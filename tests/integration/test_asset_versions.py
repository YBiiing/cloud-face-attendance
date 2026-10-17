import re


def test_pages_use_versioned_assets_and_relative_modules(client):
    for page in ['/', '/sessions.html', '/faces.html', '/checkin.html']:
        response=client.get(page)
        assert response.status_code==200
        assert response.headers['cache-control']=='no-cache'
        resources=re.findall(r'(?:src|href)="(/assets/[^\"]+)"',response.text)
        assert resources
        assert all(re.fullmatch(r'/assets/[0-9a-f]{12}/[^/]+',path) for path in resources)
        for path in resources:
            assert client.get(path).status_code==200
    path=re.search(r'src="([^"]+/sessions.js)"',client.get('/sessions.html').text).group(1)
    source=client.get(path).text
    assert "from './confirm.js'" in source
    module=client.get(path.rsplit('/',1)[0]+'/confirm.js')
    assert module.status_code==200 and 'dialog.showModal()' in module.text
