>프로젝트의 제목은 “마법학교 호그와트”이고, 게임의 성질을 띄고 있다.
>이 게임은 4개 군집의 사용자들의 데이터베이스를 재미있게 변형, 재구성, 조회하여 간단한 생존형 게임이다.
>사용자 별로 할 수 있는 게임과 기능을 달리하고, 서로 공격하는 것이 이 게임의 주된 기능이다.
>
>이 시스템을 이용하는 사용자로는 학생(student), 교수(professor), 빌런(Villain), 머글(Muggle)이 있다.
>학생은 교수가 제공하는 수업을 신청하여 수강하고 빌런과 머글을 공격할 수 있다. 
>교수는 수업 연구, 제공 및 성적을 입력한다. 
>발런은 미니게임을 통해서 공격력을 얻을 수 있고 학생과 머글을 공격할 수 있다, 
>머글은 미니주식을 통해 돈을 벌고, 그 돈으로 마법을 살 수 있으며 마법을 구매하면 공격력이 생긴다. 머글은 학생과 빌런을 공격할 수 있다.

## 1. .env 설정
자신의 local 환경에 맞게 .env 파일을 수정하세요
```
DB_NAME="project"
DB_USER="db_project"
DB_PASSWORD="!db_project"
DB_HOST="::1"
DB_PORT="5432"

SECRET_KEY=your_very_long_and_very_random_secret_key
```

## 2. server.py 실행
서버를 실행하고 127.0.0.1:5000 으로 접속하세요

## 3. Enjoy!
저희가 만든 게임을 즐겨보세요!!!!!
