def test_environment_creation(client, auth):
    r = client.post('/api/environments', headers=auth, json={'template_id':'backend'})
    assert r.status_code == 202
    assert r.json()['status'] == 'requested'


def test_idempotency(client, auth):
    h = {**auth, 'Idempotency-Key':'same-request'}
    a = client.post('/api/environments', headers=h, json={'template_id':'backend'})
    b = client.post('/api/environments', headers=h, json={'template_id':'backend'})
    assert a.json()['id'] == b.json()['id']
    assert b.status_code == 200


def test_authorization(client, auth):
    env = client.post('/api/environments', headers=auth, json={'template_id':'backend'}).json()
    client.post('/api/auth/register', json={'email':'other@example.edu','password':'another-long-password'})
    t = client.post('/api/auth/login', json={'email':'other@example.edu','password':'another-long-password'}).json()['access_token']
    r = client.get(f"/api/environments/{env['id']}", headers={'Authorization':f'Bearer {t}'})
    assert r.status_code == 404
