from pulp_ansible.app.models import AnsibleDistribution
from pulp_ansible.app.models import AnsibleRepository

legacy_repo,_ = AnsibleRepository.objects.get_or_create(name='legacy')
legacy_distro,_ = AnsibleDistribution.objects.get_or_create(
    base_path='legacy',
    defaults={
        'name': 'legacy',
        'base_path': 'legacy',
        'repository': legacy_repo
    }
)
