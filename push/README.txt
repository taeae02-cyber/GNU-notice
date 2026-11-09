푸시 알림 켜기 — 본인이 할 일 (15분, 전부 무료, 카드 없음)
==============================================================

구조: [사이트에서 알림 켬] → [Cloudflare Worker가 구독 보관] → [GitHub 수집기가 매시간 새 글을 대조해 발송] → [폰·PC 알림]

A. Cloudflare (5분)
-------------------
1. https://dash.cloudflare.com/sign-up 에서 가입 (이메일 인증까지).
2. 왼쪽 메뉴 "Workers & Pages" → "Create" → "Create Worker"
   - 이름: gnu-push   → "Deploy" (내용은 나중에 바꿈)
3. 방금 만든 Worker 화면에서 "Edit code" (또는 "</> Edit code")
   - 편집창 내용을 전부 지우고, 이 폴더의 worker.js 내용을 전부 붙여넣기 → 오른쪽 위 "Deploy"
4. Worker 화면 → "Settings" 탭
   a) "Bindings" → "Add" → "KV namespace"
      - Variable name: SUBS
      - KV namespace: "Create new namespace" 로 새로 만들기 (이름 아무거나, 예: gnu-push-subs) → Deploy/Save
   b) "Variables and Secrets" → "Add"
      - Type: Secret
      - Name: TOKEN
      - Value: 아무 긴 문자열 (아래 "토큰" 참고) → Deploy/Save
5. Worker 주소 확인: 화면 위에 https://gnu-push.<아이디>.workers.dev 같은 주소가 보임.
   브라우저로 열어보면 {"ok":true,"service":"GNU 공지 푸시 서버", ...} 가 나오면 성공.

   토큰: 비밀번호 역할. 영문+숫자 30자 정도를 아무렇게나 만들어 메모장에 적어 둠 (두 군데에 같은 값 넣어야 함).
   예: ab7Qx92kLmPz3Vt8RnEw5YhJd0Cs4Ug (이건 예시이니 직접 다르게 만들 것)

B. GitHub (3분)
---------------
저장소 → Settings → 왼쪽 "Secrets and variables" → "Actions" → "New repository secret"
  - Name: PUSH_SERVER   Value: https://gnu-push.<아이디>.workers.dev   (끝에 / 없이)
  - Name: PUSH_TOKEN    Value: 위에서 만든 토큰

C. 사이트에 서버 주소 넣기 (1분)
--------------------------------
docs/app.js 맨 위 CONFIG 의 pushServer 에 Worker 주소를 넣음:
    pushServer: "https://gnu-push.<아이디>.workers.dev",
(Claude에게 주소를 알려주면 대신 넣어 줌) → GitHub Desktop 에서 Commit → Push.

D. 확인
-------
1. 사이트 → "내 키워드" 탭 → 키워드 등록 → "푸시 알림 받기" 켬 → 브라우저가 허용 물어보면 "허용".
2. Worker 주소를 브라우저로 열면 subscribers 숫자가 1 이 됨.
3. 다음 수집(매시 7분)에서 조건에 맞는 새 글이 있으면 알림이 옴.
   바로 시험하려면 GitHub → Actions → 공지 수집 → Run workflow. (새 글이 없으면 알림도 없음)

알아둘 것
---------
- 아이폰: 사파리에서 "공유 → 홈 화면에 추가" 한 뒤 그 아이콘으로 열어야 알림을 켤 수 있음 (iOS 16.4 이상).
- 안드로이드/PC 크롬·엣지: 바로 됨. 삼성 인터넷도 됨.
- 알림은 수집 주기(1시간) 때문에 글이 올라온 뒤 최대 1시간 안에 옴.
- 무료 한도: Cloudflare Workers 하루 10만 요청, KV 읽기 10만 — 학생 수천 명이 써도 여유.
