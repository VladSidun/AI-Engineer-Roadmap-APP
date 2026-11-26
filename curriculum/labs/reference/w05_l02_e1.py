def solve(role: str, actor_id: str, tenant: str, owner_id: str, document_tenant: str, action: str) -> bool:
    if not actor_id.strip() or not tenant.strip() or tenant != document_tenant:
        return False
    if role == 'admin':
        return action in {'read', 'update', 'delete'}
    if role == 'editor':
        return action == 'read' or (action == 'update' and actor_id == owner_id)
    return role == 'viewer' and action == 'read'
