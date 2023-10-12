class DependencyCache:
    _cache = dict()

    @classmethod
    def get(cls, dep):
        if instance := cls._cache.get(dep.__name__):
            return instance

        instance = dep()
        cls._cache[dep.__name__] = instance
        return instance
