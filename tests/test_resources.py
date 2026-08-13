from app.kubernetes.resources import quota_body


def test_resource_quota_generation():
    q = quota_body('env-1','2','3Gi','5Gi',8)
    hard = q['spec']['hard']
    assert hard['limits.cpu'] == '2'
    assert hard['limits.memory'] == '3Gi'
    assert hard['requests.storage'] == '5Gi'
    assert hard['pods'] == '8'
