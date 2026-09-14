class BaseService:
    """Write operations for one model, done on behalf of `actor`.

        UserService(request.user).block_user(user)

    The helpers fill in created_by / updated_by / deleted_by. Services raise
    Django's ValidationError and PermissionDenied; the API exception handler
    turns those into 400 and 403 responses.
    """

    def __init__(self, actor=None):
        # Anonymous users and scripts write with no actor.
        self.actor = actor if getattr(actor, 'is_authenticated', False) else None

    def _create(self, model, **fields):
        return model._default_manager.create(created_by=self.actor, updated_by=self.actor, **fields)

    def _update(self, instance, **fields):
        for name, value in fields.items():
            setattr(instance, name, value)
        instance.updated_by = self.actor
        instance.save(update_fields=[*fields, 'updated_by'])
        return instance

    def _delete(self, instance):
        instance.delete(user=self.actor)
