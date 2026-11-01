# SCM B2B 포털

구매 기업과 협력업체 간 품목·계약 단가, 단가 변경 승인, 발주, A4 출력을 다루는 포털의 착수 골격이다.

업무 화면과 API는 아직 없다. 절차서 2단계(범위·권한·상태 전이·출력 견본)가 확정되기 전에는 단가·발주 규칙을 구현하지 않는다. 미결 항목은 `docs/policy-decisions.md`에 있다.

## 로컬 실행

Python 3.12를 사용한다.

```text
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- `GET /` 와 `GET /health` 는 데이터베이스 없이 응답한다.
- `DATABASE_URL` 또는 `MYSQL_URL`이 있을 때만 DB 세션을 만든다.

## Railway

배포 대상은 Railway다. 2026-11-01 기준 새 서비스는 `railway.toml`을 읽지 않으므로, 이 저장소는 루트의 `Dockerfile`로 기동한다.

1. Railway에서 새 프로젝트를 만들고 **Deploy from GitHub repo**로 `gmdcok-crypto/b2b`를 선택한다.
2. 빌드가 끝나면 서비스 **Settings → Networking**에서 **Generate Domain**을 누른다.
3. **Healthcheck Path**를 `/health`로 둔다. 이 경로는 데이터베이스를 조회하지 않는다.
4. 공개 주소의 `/health`가 `{"status":"ok"}`를 반환하면 웹 서비스 연결은 끝난 것이다.

시작 명령은 컨테이너 안에서 다음이다.

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway가 넣는 `PORT`를 사용한다. 저장소 루트에 `package.json`을 두면 Node 앱으로 오인할 수 있으니 두지 않는다.

### 데이터베이스

Railway의 기본 데이터베이스 도우미는 MySQL, PostgreSQL, Redis, MongoDB다. MariaDB는 그 목록에 없다. MariaDB 10.11을 쓰려면 같은 프로젝트에 MariaDB 서비스를 따로 두고, 데이터 디렉터리 `/var/lib/mysql`에 볼륨을 마운트한다. 이미지 태그는 `mariadb:10.11`을 기준으로 한다.

웹 서비스에는 그 데이터베이스의 **비공개** 접속 URL을 `DATABASE_URL` 또는 `MYSQL_URL`로 넣는다. `mysql://`, `mariadb://`는 애플리케이션이 `mysql+pymysql://`로 바꿔 SQLAlchemy에 전달한다. 외부에서 접속할 때만 TCP 프록시를 열고, 그 트래픽은 네트워크 송신 비용이 붙는다.

백업, 복구 목표, 호스팅 소유자는 아직 정해지지 않았다.
