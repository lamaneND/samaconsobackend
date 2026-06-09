#!/bin/bash
docker rm -f samaconso_flower 2>/dev/null || true
docker run -d --name samaconso_flower --network samaconso_net --restart unless-stopped -p 5555:5555 -e CELERY_BROKER_URL=redis://10.101.1.210:6379/0 -e CELERY_RESULT_BACKEND=redis://10.101.1.210:6379/0 -e SECRET_KEY='$3?N2LEC123' -e LDAP_SEARCH_PASSWORD='!!=++PT25@--ZmA' samaconso_api:latest celery -A app.celery_app flower --port=5555 --basic_auth=admin:admin
echo "Flower lancé : http://10.101.1.210:5555 (admin/admin)"
