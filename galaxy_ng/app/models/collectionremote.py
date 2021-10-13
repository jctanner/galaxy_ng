from django.core.validators import MinValueValidator
from django.db import models


from pulp_ansible.app.models import CollectionRemote as PulpCollectionRemote


class CollectionRemote(PulpCollectionRemote):

    download_concurrency = models.PositiveIntegerField(
        null=True,
        related_name='download_concurrency',
        validators=[MinValueValidator(
            1,
            "Download concurrency must be at least 1"
        )]
    )

    class Meta:
        default_related_name = "remotes"

    def __init__(self, *args, **kwargs):
        super(CollectionRemote, self).__init__(*args, **kwargs)
