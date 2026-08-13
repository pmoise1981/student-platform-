def test_register_and_login(client):
    r = client.post('/api/auth/register', json={'email':'a@example.edu','password':'very-secure-password'})
    assert r.status_code == 201
    r = client.post('/api/auth/login', json={'email':'a@example.edu','password':'very-secure-password'})
    assert r.status_code == 200
    assert r.json()['access_token']


def test_bad_password(client):
    client.post('/api/auth/register', json={'email':'a@example.edu','password':'very-secure-password'})
    r = client.post('/api/auth/login', json={'email':'a@example.edu','password':'wrong'})
    assert r.status_code == 401
