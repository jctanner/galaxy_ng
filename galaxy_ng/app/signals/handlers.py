"""
Signal handlers for the Galaxy application.
Those signals are loaded by
galaxy_ng.app.__init__:PulpGalaxyPluginAppConfig.ready() method.
"""

import threading
import contextlib
import logging

from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models.signals import post_delete
from django.db.models.signals import m2m_changed
from django.db.models import CharField, Value
from django.db.models.functions import Concat
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from rest_framework.exceptions import ValidationError
from django.apps import apps
from pulp_ansible.app.models import (
    AnsibleDistribution,
    AnsibleRepository,
    Collection,
    AnsibleNamespaceMetadata,
)
from galaxy_ng.app.models import Namespace, User, Team
from galaxy_ng.app.migrations._dab_rbac import copy_roles_to_role_definitions
from pulpcore.plugin.models import ContentRedirectContentGuard

from ansible_base.rbac.validators import validate_permissions_for_model
from ansible_base.rbac.models import (
    RoleDefinition,
    RoleUserAssignment,
    RoleTeamAssignment,
)
from ansible_base.rbac.triggers import dab_post_migrate
from ansible_base.rbac import permission_registry

from pulpcore.plugin.util import assign_role
from pulpcore.plugin.util import remove_role
from pulpcore.plugin.models.role import GroupRole, UserRole, Role


logger = logging.getLogger(__name__)


PULP_TO_ROLEDEF = {
    'galaxy.auditor': 'Platform Auditor',
}


ROLEDEF_TO_PULP = {
    'Platform Auditor': 'galaxy.auditor',
}


@receiver(post_save, sender=AnsibleRepository)
def ensure_retain_repo_versions_on_repository(sender, instance, created, **kwargs):
    """Ensure repository has retain_repo_versions set when created.
    retain_repo_versions defaults to 1 when not set.
    """

    if created and instance.retain_repo_versions is None:
        instance.retain_repo_versions = 1
        instance.save()


@receiver(post_save, sender=AnsibleDistribution)
def ensure_content_guard_exists_on_distribution(sender, instance, created, **kwargs):
    """Ensure distribution have a content guard when created."""

    content_guard = ContentRedirectContentGuard.objects.first()

    if created and instance.content_guard is None:
        instance.content_guard = content_guard
        instance.save()


@receiver(post_save, sender=Collection)
def create_namespace_if_not_present(sender, instance, created, **kwargs):
    """Ensure Namespace object exists when Collection object saved.
    django signal for pulp_ansible Collection model, so that whenever a
    Collection object is created or saved, it will create a Namespace object
    if the Namespace does not already exist.
    Supports use case: In pulp_ansible sync, when a new collection is sync'd
    a new Collection object is created, but the Namespace object is defined
    in galaxy_ng and therefore not created. This signal ensures the
    Namespace is created.
    """

    Namespace.objects.get_or_create(name=instance.namespace)


@receiver(post_save, sender=AnsibleNamespaceMetadata)
def associate_namespace_metadata(sender, instance, created, **kwargs):
    """
    Update the galaxy namespace when a new pulp ansible namespace
    object is added to the system.
    """

    ns, created = Namespace.objects.get_or_create(name=instance.name)
    ns_metadata = ns.last_created_pulp_metadata

    def _update_metadata():
        ns.last_created_pulp_metadata = instance
        ns.company = instance.company
        ns.email = instance.email
        ns.description = instance.description
        ns.resources = instance.resources
        ns.set_links([{"name": x, "url": instance.links[x]} for x in instance.links])
        ns.save()

    if created or ns_metadata is None:
        _update_metadata()

    elif ns.metadata_sha256 != instance.metadata_sha256:
        _update_metadata()


# ___ DAB RBAC ___

TEAM_MEMBER_ROLE = 'Galaxy Team Member'


def create_managed_roles(*args, **kwargs) -> None:
    # do not create corresponding roles for these RoleDefinitions
    with dab_rbac_signals():
        # Create the DAB-only roles
        permission_registry.create_managed_roles(apps)
        # Create any roles created by pulp post_migrate signals
        copy_roles_to_role_definitions(apps, None)


dab_post_migrate.connect(create_managed_roles, dispatch_uid="create_managed_roles")


# Signals for synchronizing the pulp roles with DAB RBAC roles
rbac_state = threading.local()

rbac_state.pulp_action = False
rbac_state.dab_action = False


@contextlib.contextmanager
def pulp_rbac_signals():
    "Used while firing signals from pulp RBAC models to avoid infinite loops"
    try:
        prior_value = rbac_state.pulp_action
        rbac_state.pulp_action = True
        yield
    finally:
        rbac_state.pulp_action = prior_value


@contextlib.contextmanager
def dab_rbac_signals():
    "Used while firing signals from DAB RBAC models to avoid infinite loops"
    try:
        prior_value = rbac_state.dab_action
        rbac_state.dab_action = True
        yield
    finally:
        rbac_state.dab_action = prior_value


def rbac_signal_in_progress():
    return bool(rbac_state.dab_action or rbac_state.pulp_action)


def copy_permissions_role_to_role(roleA, roleB):
    """Make permissions on roleB match roleA

    Our RoleDefinition and Role models, and respective permission models,
    are similiar enough to use a shortcut.
    Without knowing the type of roleA or roleB, we can inspect permission codenames
    and then just make sure they match.

    A call to this method establishes that roleA should become the source-of-truth
    """

    print(f'# copy_permissions_role_to_role a:{roleA} b:{roleB}')

    permissionsA = list(roleA.permissions.prefetch_related("content_type"))
    permissionsB = list(roleB.permissions.prefetch_related("content_type"))
    fullnamesA = set(f"{perm.content_type.app_label}.{perm.codename}" for perm in permissionsA)
    fullnamesB = set(f"{perm.content_type.app_label}.{perm.codename}" for perm in permissionsB)
    fullnames_to_add = fullnamesA - fullnamesB
    fullnames_to_remove = fullnamesB - fullnamesA
    concat_exp = Concat("content_type__app_label", Value("."), "codename", output_field=CharField())

    # The m2m manager needs ids or objects so we need to work with the destination permission model
    # Optimization node: this should never simultaneously have both additions AND removals,
    # so there is no point in optimizing for that case
    permission_modelB = roleB._meta.get_field("permissions").related_model
    if fullnames_to_add:
        ids_to_add = list(
            permission_modelB.objects.annotate(fullname=concat_exp)
            .filter(fullname__in=fullnames_to_add)
            .values_list("id", flat=True)
        )
        roleB.permissions.add(*ids_to_add)

    if fullnames_to_remove:
        ids_to_remove = list(
            permission_modelB.objects.annotate(fullname=concat_exp)
            .filter(codename__in=fullnames_to_remove)
            .values_list("id", flat=True)
        )
        roleB.permissions.remove(*ids_to_remove)


# Pulp Role to DAB RBAC RoleDefinition objects
@receiver(post_save, sender=Role)
def copy_role_to_role_definition(sender, instance, created, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""

    print(f'copy_role_to_role_definition sender:{sender} instance:{instance}')

    if rbac_signal_in_progress():
        return
    with pulp_rbac_signals():

        roledef_name = PULP_TO_ROLEDEF(instance.name, instance.name)
        rd = RoleDefinition.objects.filter(name=roledef_name).first()
        if not rd:
            RoleDefinition.objects.create(
                name=roledef_name,
                managed=instance.locked,
                description=instance.description or instance.name,
            )
        # TODO: other fields? like description


@receiver(post_delete, sender=Role)
def delete_role_to_role_definition(sender, instance, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""

    print(f'# delete_role_to_role_definition sender:{sender} instance:{instance}')

    if rbac_signal_in_progress():
        return
    with dab_rbac_signals():
        roledef_name = PULP_TO_ROLEDEF(instance.name, instance.name)
        rd = RoleDefinition.objects.filter(name=roledef_name).first()
        if rd:
            rd.delete()


def copy_permission_role_to_rd(instance, action, model, pk_set, reverse, **kwargs):

    print(f'# copy_permission_role_to_rd instance:{instance} action:{action} model:{model} pk_set:{pk_set} reverse:{reverse}')

    if rbac_signal_in_progress():
        return
    if action.startswith("pre_"):
        return
    if reverse:
        # NOTE: this should not work because of DAB RBAC signals either
        # but this exception should alert us to any problems via downstream testing
        # hopefully, if that is generalized
        raise RuntimeError(
            "Removal of permssions through reverse relationship"
            + " not supported due to galaxy_ng signals"
        )

    roledef_name = PULP_TO_ROLEDEF(instance.name, instance.name)
    rd = RoleDefinition.objects.filter(name=roledef_name).first()
    if rd:
        copy_permissions_role_to_role(instance, rd)


m2m_changed.connect(copy_permission_role_to_rd, sender=Role.permissions.through)


# DAB RBAC RoleDefinition objects to Pulp Role objects


@receiver(post_save, sender=RoleDefinition)
def copy_role_definition_to_role(sender, instance, created, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""

    print(f'# copy_role_definition_to_role sender:{sender} instance:{instance} created:{created}')

    if rbac_signal_in_progress():
        return
    with dab_rbac_signals():
        role_name = ROLEDEF_TO_PULP(instance.name, instance.name)
        role = Role.objects.filter(name=role_name).first()
        if not role:
            Role.objects.create(name=role_name)
        # TODO: other fields? like description


@receiver(post_delete, sender=RoleDefinition)
def delete_role_definition_to_role(sender, instance, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""

    print(f'# delete_role_definition_to_role sender:{sender} instance:{instance}')

    if rbac_signal_in_progress():
        return
    with dab_rbac_signals():
        role_name = ROLEDEF_TO_PULP(instance.name, instance.name)
        role = Role.objects.filter(name=role_name).first()
        if role:
            role.delete()


def copy_permission_rd_to_role(instance, action, model, pk_set, reverse, **kwargs):

    print(f'# copy_permission_rd_to_role instance:{instance} action:{action} model:{model} pk_set:{pk_set} reverse:{reverse}')

    if rbac_signal_in_progress():
        return
    if action.startswith("pre_"):
        return
    if reverse:
        # NOTE: this should not work because of DAB RBAC signals either
        # but this exception should alert us to any problems via downstream testing
        #  hopefully, if that is generalized
        raise RuntimeError(
            "Removal of permssions through reverse relationship"
            + " not supported due to galaxy_ng signals"
        )

    role_name = ROLEDEF_TO_PULP(instance.name, instance.name)
    role = Role.objects.filter(name=role_name).first()
    if role:
        copy_permissions_role_to_role(instance, role)


m2m_changed.connect(copy_permission_rd_to_role, sender=RoleDefinition.permissions.through)


# Pulp UserRole and TeamRole to DAB RBAC assignments


def lazy_content_type_correction(rd, obj):
    """Implements special behavior because pulp roles have no content type

    So this will apply the content_type of the first object given an object-assignment
    only under certain non-conflicting conditions"""
    if (obj is None) or rd.content_type_id:
        # If this is a system role assignment, or has already been corrected,
        # then nothing needs to be corrected
        return

    if rd.name in settings.ANSIBLE_BASE_JWT_MANAGED_ROLES:
        return
    if ((obj is None) and (rd.content_type_id is None)) or \
            (rd.content_type_id and obj._meta.model_name == rd.content_type.model):
        return  # type already matches with intent, so nothing to do here, do not even log
    if not rd.user_assignments.exists():
        ct = ContentType.objects.get_for_model(obj)
        try:
            # If permissions will not pass the validator, then we do not want to do this
            validate_permissions_for_model(list(rd.permissions.all()), ct)
        except ValidationError as exc:
            # import traceback; traceback.print_stack()
            logger.warning(
                f'Assignment to {rd.name} for {type(obj)}'
                + f' violates a DAB role validation rule: {str(exc)}'
            )
            return
        rd.content_type = ct
        rd.save(update_fields=['content_type'])
    else:
        logger.warning(
            f'Assignment to {rd.name} for {type(obj)}'
            + ' mis-matches with existing assignments'
        )


@receiver(post_save, sender=UserRole)
def copy_pulp_user_role(sender, instance, created, **kwargs):
    """When a pulp role is granted to a user, grant the equivalent dab role."""

    print(f'# copy_pulp_user_role sender:{sender} instance:{instance} created:{created}')

    # FIXME - this is a temporary workaround to allow on-demand
    #   assigment of task roles to users from pulpcore's AFTER_CREATE
    #   hook on the Task model which calls ...
    #   self.add_roles_for_object_creator("core.task_user_dispatcher")
    if instance.role.name == 'core.task_user_dispatcher':
        return

    if rbac_signal_in_progress():
        print(f'# IN PROGRESS - SKIP')
        return
    with pulp_rbac_signals():
        roledef_name = PULP_TO_ROLEDEF.get(instance.role.name, instance.role.name)
        print(f'# ROLEDEF_NAME:{roledef_name}')
        rd = RoleDefinition.objects.filter(name=roledef_name).first()
        if rd:
            if instance.content_object:
                lazy_content_type_correction(rd, instance.content_object)
                rd.give_permission(instance.user, instance.content_object)
            else:
                rd.give_global_permission(instance.user)


@receiver(post_delete, sender=UserRole)
def delete_pulp_user_role(sender, instance, **kwargs):

    print(f'# delete_pulp_user_role sender:{sender} instance:{instance}')

    if rbac_signal_in_progress():
        return
    with pulp_rbac_signals():
        roledef_name = PULP_TO_ROLEDEF.get(instance.role.name, instance.role.name)
        rd = RoleDefinition.objects.filter(name=roledef_name).first()
        print(f'delete_pulp_user_role sender.user:{sender.user} instance.user:{instance.user}')
        if rd:
            if instance.content_object:
                try:
                    rd.remove_permission(instance.user, instance.content_object)
                except Exception as e:
                    logger.warning(e)
            else:
                try:
                    rd.remove_global_permission(instance.user)
                except Exception as e:
                    logger.warning(e)


@receiver(post_save, sender=GroupRole)
def copy_pulp_group_role(sender, instance, created, **kwargs):

    print(f'# copy_pulp_group_role sender:{sender} instance:{instance} created:{created}')

    if rbac_signal_in_progress():
        return
    with pulp_rbac_signals():
        roledef_name = PULP_TO_ROLEDEF.get(instance.role.name, instance.role.name)
        rd = RoleDefinition.objects.filter(name=roledef_name).first()
        if rd and hasattr(instance.group, "team"):
            if instance.content_object:
                rd.give_permission(instance.group.team, instance.content_object)
            else:
                rd.give_global_permission(instance.group.team)


@receiver(post_delete, sender=GroupRole)
def delete_pulp_group_role(sender, instance, **kwargs):

    print(f'# delete_pulp_group_role sender:{sender} instance:{instance}')

    if rbac_signal_in_progress():
        return
    with pulp_rbac_signals():
        roledef_name = PULP_TO_ROLEDEF.get(instance.role.name, instance.role.name)
        rd = RoleDefinition.objects.filter(name=roledef_name).first()
        if rd and hasattr(instance.group, "team"):
            if instance.content_object:
                rd.remove_permission(instance.group.team, instance.content_object)
            else:
                rd.remove_global_permission(instance.group.team)


# DAB RBAC assignments to pulp UserRole TeamRole


def _get_pulp_role_kwargs(assignment):
    kwargs = {}
    if assignment.object_id:
        kwargs["obj"] = assignment.content_object
    if isinstance(assignment, RoleUserAssignment):
        entity = assignment.user
    elif isinstance(assignment, RoleTeamAssignment):
        entity = assignment.team.group
    else:
        raise Exception(f"Could not find entity for DAB assignment {assignment}")
    role_name = ROLEDEF_TO_PULP.get(assignment.role_definition.name, assignment.role_definition.name)
    return (role_name, entity), kwargs


def _apply_dab_assignment(assignment):
    role_name = ROLEDEF_TO_PULP.get(assignment.role_definition.name, assignment.role_definition.name)
    if not Role.objects.filter(name=role_name).exists():
        return  # some platform roles will not have matching pulp roles
    args, kwargs = _get_pulp_role_kwargs(assignment)
    assign_role(*args, **kwargs)


def _unapply_dab_assignment(assignment):
    role_name = ROLEDEF_TO_PULP.get(assignment.role_definition.name, assignment.role_definition.name)
    if not Role.objects.filter(name=role_name).exists():
        return  # some platform roles will not have matching pulp roles
    args, kwargs = _get_pulp_role_kwargs(assignment)
    remove_role(*args, **kwargs)


@receiver(post_save, sender=RoleUserAssignment)
def copy_dab_user_role_assignment(sender, instance, created, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""

    print(f'# copy_dab_user_role_assignment sender:{sender} instance:{instance} created:{created}')

    if rbac_signal_in_progress():
        print(f'# INPROGRESS - SKIP')
        return
    with dab_rbac_signals():
        if instance.role_definition.name == TEAM_MEMBER_ROLE and \
                isinstance(instance, RoleUserAssignment):
            instance.content_object.group.user_set.add(instance.user)
            print(f'# team memer role stuff - skipping')
            return
        print(f'# CALL _apply_dab_assignment')
        _apply_dab_assignment(instance)


@receiver(post_delete, sender=RoleUserAssignment)
def delete_dab_user_role_assignment(sender, instance, **kwargs):
    """When a dab role is revoked from a user, revoke the equivalent pulp role."""

    print(f'# delete_dab_user_role_assignment sender:{sender} instance:{instance}')

    if rbac_signal_in_progress():
        return
    with dab_rbac_signals():
        if instance.role_definition.name == TEAM_MEMBER_ROLE and \
                isinstance(instance, RoleUserAssignment):
            # If the assignment does not have a content_object then it may be a global group role
            # this type of role is not compatible with DAB RBAC and what we do is still TBD
            if instance.content_object:
                instance.content_object.group.user_set.remove(instance.user)
                return
        _unapply_dab_assignment(instance)


@receiver(post_save, sender=RoleTeamAssignment)
def copy_dab_team_role_assignment(sender, instance, created, **kwargs):
    """When a dab role is granted to a team, grant the equivalent pulp role."""

    print(f'# copy_dab_team_role_assignment sender:{sender} instance:{instance} created:{created}')

    if rbac_signal_in_progress():
        return
    with dab_rbac_signals():
        _apply_dab_assignment(instance)


@receiver(post_delete, sender=RoleTeamAssignment)
def delete_dab_team_role_assignment(sender, instance, **kwargs):
    """When a dab role is revoked from a team, revoke the equivalent pulp role."""

    print(f'# delete_dab_team_role_assignment sender:{sender} instance:{instance}')

    if rbac_signal_in_progress():
        return
    with dab_rbac_signals():
        _unapply_dab_assignment(instance)


# Connect User.groups to the role in DAB

def copy_dab_group_to_role(instance, action, model, pk_set, reverse, **kwargs):

    print(f'# copy_dab_group_to_role instance:{instance} action:{action} model:{model} pk_set:{pk_set} reverse:{reverse}')

    if rbac_signal_in_progress():
        return
    if action.startswith("pre_"):
        return

    member_rd = RoleDefinition.objects.get(name=TEAM_MEMBER_ROLE)
    if reverse:
        # NOTE: for we might prefer to use pk_set
        # but it appears to be incorrectly empty on the reverse signal,
        # the models itself on post_ actions seems good so we use that
        team = Team.objects.get(group_id=instance.pk)
        current_dab_members = set(
            assignment.user for assignment in RoleUserAssignment.objects.filter(
                role_definition=member_rd, object_id=team.pk
            )
        )
        desired_members = set(instance.user_set.all())
        users_to_add = desired_members - current_dab_members
        users_to_remove = current_dab_members - desired_members
        with dab_rbac_signals():
            for user in users_to_add:
                member_rd.give_permission(user, team)
            for user in users_to_remove:
                member_rd.remove_permission(user, team)
        return

    with dab_rbac_signals():
        if action == 'post_add':
            for group_id in pk_set:
                team = Team.objects.get(group_id=group_id)
                member_rd.give_permission(instance, team)
        elif action == 'post_remove':
            for group_id in pk_set:
                team = Team.objects.get(group_id=group_id)
                member_rd.remove_permission(instance, team)
        elif action == 'post_clear':
            qs = RoleUserAssignment.objects.filter(role_definition=member_rd, user=instance)
            for assignment in qs:
                member_rd.remove_permission(instance, assignment.content_object)


m2m_changed.connect(copy_dab_group_to_role, sender=User.groups.through)
