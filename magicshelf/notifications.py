"""Local update notices; no network calls or user-usage reporting."""
from .contracts import require


def ready_notices(state, modules, cached):
    result = []
    for module in modules:
        key = module['id']
        pending = state['pending_updates'].get(key)
        if not (pending and module.get('enabled') and module.get('subscribed')
                and module.get('update_status') == 'ready' and cached(key, pending).is_file()):
            continue
        token = pending['version'] + ':' + pending['sha256']
        saved = state.get('update_notices', {}).get(key, {})
        matching = saved.get('token') == token
        result.append(dict(id=key, name=module['name'], version=pending['version'], token=token,
                           announced=matching and bool(saved.get('announced')),
                           dismissed=matching and bool(saved.get('dismissed')),
                           message='Keep playing. This update installs automatically when you turn the creation Off.'))
    return result


def acknowledge(manager, key, token, action):
    require(action in ('announced', 'later'), 'Unknown update-notice action')
    with manager.transaction():
        notice = next((n for n in manager.snapshot()['update_notices'] if n['id'] == key and n['token'] == token), None)
        require(notice is not None, 'This update notice is no longer current')
        records = manager.state.setdefault('update_notices', {})
        previous = records.get(key, {})
        records[key] = dict(token=token, announced=True,
                            dismissed=action == 'later' or (previous.get('token') == token and bool(previous.get('dismissed'))))
        # Keep the ledger bounded to installed creations. Dismissing a notice
        # never removes the verified pending download or changes running state.
        manager.state['update_notices'] = {k:v for k,v in records.items() if k in manager.state['modules']}
        manager.save()
    return manager.snapshot()
