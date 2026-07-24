class _Scheduler:
    def scheduled_job(self, *args, **kwargs):
        def deco(func):
            return func
        return deco


scheduler = _Scheduler()
