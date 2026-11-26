def can_update(actor_tenant: str, actor_role: str, document_tenant: str) -> bool:
    return actor_role == 'owner' and actor_tenant == document_tenant

if __name__ == '__main__':
    cases = [('owner','north','owner'), ('viewer','north','viewer'), ('outsider','south','owner')]
    for label, tenant, role in cases:
        print(label, 'allow' if can_update(tenant, role, 'north') else 'deny')
