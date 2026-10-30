def test_health(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_health_answers_any_host(client):
    # Load balancer probes address the container by its private IP.
    response = client.get('/api/health', HTTP_HOST='172.26.15.118:8000')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_other_paths_still_check_the_host(client):
    response = client.get('/api/places', {'text': 'Chicago'}, HTTP_HOST='172.26.15.118:8000')
    assert response.status_code == 400
