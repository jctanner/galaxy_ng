from pulp_ansible.app.models import GitRemote

class NGRole(GitRemote):

    class Meta(GitRemote.Meta):
        default_related_name = 'gitremote'
