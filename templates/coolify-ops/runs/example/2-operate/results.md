# Operation results: redeploy acme-website

Followed `playbooks/redeploy-app.md`.

1. Confirmed the target with the user from the mirror: `acme-website`,
   uuid `mk3v7q9x2c5b8n1z4f6h0j2l`, project Acme.
2. User approved the write call. Triggered
   `GET /deploy?uuid=mk3v7q9x2c5b8n1z4f6h0j2l`. Response:
   `deployment_uuid: d4g8s2w6e0r4t8y2u6i0o4p8`, status `queued`.
3. Polled `GET /deployments/d4g8s2w6e0r4t8y2u6i0o4p8`:
   - Poll 1 (10 s): `in_progress`. Logs showed the harmless
     `Error response from daemon: No such container:
     d4g8s2w6e0r4t8y2u6i0o4p8` line early on, as the playbook predicts.
   - Poll 2 (95 s): `in_progress`, build running (new commit SHA, so no
     image reuse this time).
   - Poll 3 (240 s): `finished`. Rolling update warned about an orphan
     container from the previous deployment; Coolify removed it itself.
4. Verified: `GET /applications/mk3v7q9x2c5b8n1z4f6h0j2l` returned status
   `running:unknown` (health check unknown, expected per the playbook).
   HTTP GET on `https://acme-website.example.com` returned 200 and the
   new content.

Surprise worth keeping: a deploy with a new commit took about 4 minutes;
the playbook's note about same-SHA instant finishes held in reverse.
