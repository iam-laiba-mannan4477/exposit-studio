# Running Exposit Studio on AWS EC2 (optional)

Nothing here is needed to use the studio on your laptop. The files are in `deploy/` and `Dockerfile`.

**Status: written and reviewed, but not yet built or run.** The development sandbox could not reach Docker Hub. Expect to fix small issues on the first build.

## Security first

The studio has **no sign-in of its own**. On a server it must never be reachable directly. The Compose file publishes only Caddy, which:
- obtains and renews an HTTPS certificate for your domain automatically, and
- asks for a user name and password before passing any request on.

Keep `EXPOSIT_HOST=0.0.0.0` inside the container only. The studio container exposes port 8600 to the Compose network, never to the host.

## 1. Server

- Instance: **t3.large** (2 vCPU, 8 GB) matches the laptop. **c7i.xlarge** (4 vCPU) renders faster. Check current prices for your region on the EC2 pricing page before choosing. Stop the instance when not in use to stop compute charges (storage is still charged).
- Disk: 30 GB gp3.
- OS: Ubuntu 24.04 LTS.
- Security group: inbound **22** (your IP only), **80** and **443** (anywhere, for HTTPS). Nothing else.
- A domain or subdomain with an **A record** pointing to the instance's Elastic IP.

## 2. Install Docker and copy the project

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER && newgrp docker
# copy the project (from your laptop: scp -r exposit-studio ubuntu@<ip>:~/ ), then:
cd ~/exposit-studio
touch .env                       # optional keys; may stay empty
```

## 3. Configure and start

```bash
cd deploy
cp server.env.example server.env
docker run --rm caddy:2 caddy hash-password --plaintext 'a-long-password'
nano server.env                  # set EXPOSIT_DOMAIN, EXPOSIT_USER, and EXPOSIT_PASSWORD_HASH (double every $)
docker compose --env-file server.env up -d --build
docker compose logs -f           # wait for "certificate obtained"
```

Open `https://<your domain>` and sign in with the user name and password.

## 4. Data, backups, updates

- Everything (database, productions, renders) is in the Docker volume `deploy_exposit-data`. Back it up with:
  `docker run --rm -v deploy_exposit-data:/d -v $PWD:/b alpine tar czf /b/exposit-data.tgz -C /d .`
  and copy the archive to S3 (`aws s3 cp exposit-data.tgz s3://<bucket>/`). EBS snapshots are another option.
- To update: copy the new project over, then `docker compose --env-file server.env up -d --build`.
- Keys go in the project's `.env` on the server (or AWS Secrets Manager / SSM Parameter Store injected as environment variables), never in the image.

## 5. Daily Scout on the server

The studio's own daily timer works while the container runs (Settings or the Scout page). Alternatively, a host cron entry:
`10 4 * * * docker compose -f ~/exposit-studio/deploy/docker-compose.yml exec -T exposit python -m exposit.cli scout`

## 6. Growing later (designed for, not built)

- **Object storage**: productions are plain folders, so exports can be synced to S3 after approval without changing the pipeline.
- **Remote render workers**: the renderer takes a scene specification plus narration timing and returns a clip file named by its content hash. A worker that runs `render_clip` on another machine and uploads the clip can replace the local call. The job queue is a single SQLite table today; a multi-machine setup would move it to a proper queue (for example SQS).
- **More users**: add real authentication in front of the API (for example an identity provider through the reverse proxy) before sharing the studio with anyone else.
