import re
import json

from theblues import charmstore


class CharmNotFound(Exception):
    pass


AVAILABLE_INCLUDES = [
    'bundle-machine-count',
    'bundle-metadata',
    'bundle-unit-count',
    'bundles-containing',
    'charm-actions',
    'charm-config',
    'charm-metadata',
    'common-info',
    'extra-info',
    'revision-info',
    'stats',
    'supported-series',
    'manifest',
    'tags',
    'promulgated',
    'perm',
    'id',
]


class CharmStore(object):
    def __init__(self, api='https://api.jujucharms.com/v4'):
        super(CharmStore, self).__init__()
        self.theblues = charmstore.CharmStore(api)

    def requires(self, interfaces=[], limit=None):
        return self.interfaces(requires=interfaces)

    def provides(self, interfaces=[], limit=None):
        return self.interfaces(provides=interfaces)

    def interfaces(self, requires=[], provides=[], limit=None):
        params = {}
        if type(requires) == str:
            requires = [requires]
        if type(provides) == str:
            provides = [provides]

        if type(requires) is not list or type(provides) is not list:
            raise Exception('requires/provides must be either a str or list')

        if requires:
            params['requires'] = '&requires='.join(requires)
        if provides:
            params['provides'] = '&provides='.join(provides)

        return self.search(params)

    def search(self, text=None, includes=None, doc_type=None, limit=None,
               autocomplete=False, promulgated_only=False, tags=None,
               sort=None, owner=None, series=None):

        if not includes:
            includes = AVAILABLE_INCLUDES

        result = self.theblues.search(**kwargs)

        return [Charm.from_data(charm) for charm in result]

    def approved(self):
        return self.search(None, promulgated_only=True)


class Entity(object):
    @classmethod
    def from_data(cls, data):
        e = cls()
        e.load(data)

        return e

    def __init__(self, id=None, api='https://api.jujucharms.com/v4'):
        self.id = None
        self.name = None
        self.owner = None
        self.series = None
        self.maintainer = None
        self.revision = None
        self.url = None

        self.approved = False
        self.tags = None
        self.source = None

        self.files = []

        self.stats = {}

        self.raw = {}
        self.theblues = charmstore.CharmStore(api)

        if id:
            self.load(
                self.theblues._meta(id.replace('cs:', ''),
                                    AVAILABLE_INCLUDES)
            )

    def revisions(self):
        data = self.raw.get('revision-info', {}).get('Revisions', [])
        return [self.__class__(e) for e in data]

    def file(self, path):
        if path not in self.files:
            raise IOError(0, 'No such file in %s' self.__class__.__name__.lower(), path)

        return self.theblues._get(self.theblues.file_url(self.url, path)).text

    def load(self, data):
        id = data.get('id', {})
        self.id = id.get('Id')
        self.url = id.get('Id').replace('cs:', '')
        self.name = id.get('Name')
        self.revision = id.get('Revision', 0)
        self.series = id.get('Series')

        self.tags = data.get('Tags', {}).get('Tags', [])

        extra_info = data.get('extra-info', {})
        self.source = extra_info.get('bzr-url')

        manifest = data.get('manifest', [])
        self.files = [f.get('Name') for f in manifest]

        self.approved = data.get('promulgated', {}).get('Promulgated', False)

        self.raw = data


class Charm(Entity):
    def __init__(self, id=None, api='https://api.jujucharms.com/v4'):
        self.summary = None
        self.description = None

        self.subordinate = False
        self.provides = {}
        self.requires = {}
        self.peers = {}

        self.actions = {}
        self.config = {}

        self.bundles = []
        self.terms = []

        super(Charm, self).__init__(id, api)

    def related(self):
        data = self.raw.get('charm-related')
        related = {}

        for relation, interfaces in data.items():
            related[relation.lower()] = {}
            for interface, charms in interfaces.items():
                related[relation][interface] = []
                for c in charms:
                    related[relation][interface].append(Charm(c.get['Id']))

        return related

    def load(self, charm_data):
        if 'charm-metadata' not in charm_data:
            raise CharmNotFound('Not a valid charm payload')

        super(Charm, self).load(charm_data)

        metadata = self.raw.get('charm-metadata')

        self.description = metadata.get('Description')
        self.summary = metadata.get('Summary')
        self.subordinate = metadata.get('Subordinate', False)
        self.terms = metadata.get('Terms', [])

        for rel, d in metadata.get('Provides', {}).items():
            self.provides[rel] = {k.lower(): v for k, v in d.items()}

        for rel, d in metadata.get('Requires', {}).items():
            self.requires[rel] = {k.lower(): v for k, v in d.items()}

        for rel, d in metadata.get('Peers', {}).items():
            self.peers[rel] = {k.lower(): v for k, v in d.items()}

        action_spec = self.raw.get('charm-actions', {}).get('ActionSpecs')
        if action_spec:
            self.actions = action_spec

        config_options = self.raw.get('charm-config', {}).get('Options')
        if config_options:
            self.config = config_options

    def __str__(self):
        return json.dumps(self.raw, indent=2)

    def __repr__(self):
        return '<Charm %s>' % self.id