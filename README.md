# SCM B2B 포털

구매 기업과 협력업체 간 품목·계약 단가, 단가 변경 승인, 발주, A4 출력을 다루는 포털이다.

화면 파일은 `web/`에 있다. Railway는 `main` 브랜치의 저장소 루트에서 이 화면과 API를 한 서비스로 띄운다. Netlify는 같은 화면을 따로 배포할 때 쓴다. 단가·발주 규칙은 아직 서버에 없다. 미결 항목은 `docs/policy-decisions.md`에 있다.

## 로컬 실행

Python 3.12를 사용한다.

```text
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

화면은 `http://127.0.0.1:8000` 이다. `GET /health`는 같은 주소에서 응답한다.

화면은 설치형 PWA다. `manifest.webmanifest`와 `sw.js`가 화면 껍데기를 보관한다. 발주·단가 같은 업무 데이터는 오프라인에서 수정하지 않는다.

인증은 JWT 액세스 토큰이다. `JWT_SECRET`, `AUTH_USERNAME`, `AUTH_PASSWORD`가 모두 있으면 로그인을 요구하고, 토큰은 `Authorization: Bearer`로 보낸다. 하나라도 없으면 로그인 없이 샘플 화면을 연다. 계정 테이블과 리프레시 토큰은 아직 없다.

- `GET /health`는 데이터베이스를 조회하지 않는다.
- `DATABASE_URL` 또는 `MYSQL_URL`이 있을 때만 DB 세션을 만든다.

## Netlify

같은 GitHub 저장소 `gmdcok-crypto/b2b`를 연결한다. 빌드 설정은 `netlify.toml`이 정한다.

- Publish directory: `web`
- Build command: `node scripts/write-frontend-config.js`
- 환경 변수 `API_BASE`: Railway가 발급한 API 공개 URL. 끝에 슬래시는 없어도 된다.

예: `API_BASE=https://scm-api.up.railway.app`

빌드가 `web/config.js`에 이 주소를 넣는다. 주소를 바꾼 뒤에는 Netlify를 다시 배포한다.

## Railway

브랜치는 `main`, Root Directory는 비운다. 저장소 루트의 `Dockerfile`이 화면과 API를 함께 띄운다. 백엔드 폴더를 따로 두지 않는다.

1. 새 프로젝트에서 **Deploy from GitHub repo**로 `gmdcok-crypto/b2b`의 `main`을 선택한다.
2. Root Directory는 저장소 루트로 둔다.
3. **Generate Domain**으로 공개 주소를 만든다. 그 주소의 `/`가 구매 화면이고 `/health`가 API 상태다.
4. Netlify를 함께 쓰면, Netlify `API_BASE`에 이 공개 주소를 넣고 Railway `CORS_ORIGINS`에 Netlify 주소를 넣는다.

예: `CORS_ORIGINS=https://gstec.netlify.app`

`https://gstec.netlify.app`과 로컬 화면 주소 `http://127.0.0.1:8888`, `http://localhost:8888`은 기본으로 허용한다. 그 밖의 출처는 `CORS_ORIGINS`에 있을 때만 브라우저 요청이 통과한다.

시작 명령은 다음이다.

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

저장소 루트에 `package.json`을 두면 Railway가 Node 앱으로 볼 수 있으니 두지 않는다.

### 데이터베이스

Railway의 기본 데이터베이스 도우미는 MySQL, PostgreSQL, Redis, MongoDB다. MariaDB는 그 목록에 없다. MariaDB 10.11을 쓰려면 같은 프로젝트에 MariaDB 서비스를 따로 두고, 데이터 디렉터리 `/var/lib/mysql`에 볼륨을 마운트한다. 이미지 태그는 `mariadb:10.11`을 기준으로 한다.

API 서비스에는 그 데이터베이스의 **비공개** 접속 URL을 `DATABASE_URL` 또는 `MYSQL_URL`로 넣는다. `mysql://`, `mariadb://`는 애플리케이션이 `mysql+pymysql://`로 바꿔 SQLAlchemy에 전달한다.

백업, 복구 목표, 호스팅 소유자는 아직 정해지지 않았다.
