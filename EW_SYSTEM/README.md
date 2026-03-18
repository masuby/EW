# EW_SYSTEM (Java Spring Boot + Angular)

## Run locally (Docker Compose)

From the `EW_SYSTEM/` folder:

```sh
docker compose up --build
```

Services:
- `frontend`: http://localhost:4200
- `backend`: http://localhost:8080
- `minio`: http://localhost:9000 (S3-compatible)

## Default credentials

Backend bootstraps an `admin` user when `security.users.list` is empty.

- Username: `admin`
- Password: `Admin123`

JWT secret (dev): `dev-only-secret-change-me`

## Environment variables (backend)

Key variables used by the compose file:
- `EW_JWT_SECRET`
- `EW_DEV_ADMIN_PASSWORD`
- `EW_STORAGE_TYPE` (set to `s3` for MinIO; `local` for disk)
- `EW_S3_ENDPOINT`, `EW_S3_REGION`, `EW_S3_BUCKET`, `EW_S3_ACCESS_KEY`, `EW_S3_SECRET_KEY`
- `EW_GEODATA_DIR=/app/assets/geodata` (mounted from `../assets/geodata`)

## Notes

1. DOCX -> PDF conversion uses headless LibreOffice (`soffice`). The backend container installs LibreOffice.
2. The map intersection logic loads `assets/geodata/gadm41_TZA_1.json.zip` and `gadm41_TZA_2.json.zip`.

