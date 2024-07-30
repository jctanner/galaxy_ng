"""
Signal handlers for the Galaxy application.
Those signals are loaded by
galaxy_ng.app.__init__:PulpGalaxyPluginAppConfig.ready() method.
"""

import threading
import contextlib

from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models.signals import post_delete
from pulp_ansible.app.models import (
    AnsibleDistribution,
    AnsibleRepository,
    Collection,
    AnsibleNamespaceMetadata,
)
from galaxy_ng.app.models import Namespace
from pulpcore.plugin.models import ContentRedirectContentGuard

from ansible_base.rbac.models import RoleTeamAssignment
from ansible_base.rbac.models import RoleUserAssignment
from ansible_base.rbac.models import RoleDefinition
from pulpcore.plugin.util import assign_role
from pulpcore.plugin.util import remove_role


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


# Pulp Role to DAB RBAC RoleDefinition objects


@receiver(post_save, sender=Role)
def copy_role_to_role_definition(sender, instance, created, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""
    if rbac_state.pulp_action:
        return
    with pulp_rbac_signals():
        rd = RoleDefinition.objects.filter(name=instance.name).first()
        if not rd:
            RoleDefinition.objects.create(name=instance.name)
        # TODO: other fields? like description


# DAB RBAC RoleDefinition objects to Pulp Role objects


@receiver(post_save, sender=RoleDefinition)
def copy_role_definition_to_role(sender, instance, created, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""
    if rbac_state.dab_action:
        return
    with dab_rbac_signals():
        role = Role.objects.filter(name=instance.name).first()
        if not role:
            Role.objects.create(name=instance.name)
        # TODO: other fields? like description


@receiver(post_delete, sender=RoleDefinition)
def delete_role_definition_to_role(sender, instance, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""
    if rbac_state.dab_action:
        return
    with dab_rbac_signals():
        role = Role.objects.filter(name=instance.name).first()
        if role:
            role.delete()


# m2m_changed
# - adding
# - removing
# post_delete


# Pulp UserRole and TeamRole to DAB RBAC assignments

# TODO:
# - UserRole deletion
# - TeamRole creation
# - TeamRole deletion


@receiver(post_save, sender=UserRole)
def copy_pulp_user_role(sender, instance, created, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""
    if rbac_state.pulp_action:
        return
    with pulp_rbac_signals():
        rd = RoleDefinition.objects.get(name=instance.role.name)
        if instance.content_object:
            rd.give_permission(instance.user, instance.content_object)
        else:
            rd.give_global_permission(instance.user)


# DAB RBAC assignments to pulp UserRole TeamRole


@receiver(post_save, sender=RoleUserAssignment)
def copy_dab_user_role(sender, instance, created, **kwargs):
    """When a dab role is granted to a user, grant the equivalent pulp role."""
    if rbac_state.dab_action:
        return
    with dab_rbac_signals():
        assign_role(instance.role_definition.name, instance.user)


@receiver(post_delete, sender=RoleUserAssignment)
def delete_dab_user_role(sender, instance, **kwargs):
    """When a dab role is revoked from a user, revoke the equivalent pulp role."""
    if rbac_state.dab_action:
        return
    with dab_rbac_signals():
        remove_role(instance.role_definition.name, instance.user)


@receiver(post_save, sender=RoleTeamAssignment)
def copy_dab_team_role(sender, instance, created, **kwargs):
    """When a dab role is granted to a team, grant the equivalent pulp role."""
    if rbac_state.dab_action:
        return
    with dab_rbac_signals():
        assign_role(instance.role_definition.name, instance.team.group)


@receiver(post_delete, sender=RoleTeamAssignment)
def delete_dab_team_role(sender, instance, **kwargs):
    """When a dab role is revoked from a team, revoke the equivalent pulp role."""
    if rbac_state.dab_action:
        return
    with dab_rbac_signals():
        remove_role(instance.role_definition.name, instance.team.group)
