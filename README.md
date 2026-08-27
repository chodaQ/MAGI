MAGI
====

소스 코드를 넣으면, 그 목적에 딱 필요한 만큼만 남긴 최소 구성 리눅스 커널을 자동으로 빌드해주는 도구입니다.
정적 분석으로 프로그램이 실제로 쓰는 시스템 기능을 판별하고, 그에 맞는 최소 Kconfig 구성과 (선택적으로) 실제 커널 이미지까지 생성합니다.

Quick Start
-----------

* 코드가 실제로 쓰는 커널 기능 확인: `magi analyze ./my_project`
* 최소 Kconfig 조각(fragment) 생성: `magi build ./my_project --out magi.config`
* 실제 커널 소스에 대해 `.config` + 빌드 + QEMU 부팅까지: [사용법](#사용법) 참고
* 버그 리포트: 이 저장소의 Issues (또는 소스에 코멘트로 남겨주세요)
Essential Documentation
------------------------

모두가 한 번은 읽어야 할 문서:

* 왜 만들었는가: [왜 만들었는가](#왜-만들었는가)
* 기존 도구(`localmodconfig`, `tinyconfig`)와 뭐가 다른가: [기존 접근과의 차이](#기존-접근과의-차이)
* 설치 및 빌드 요구사항: [설치](#설치)
* 라이선스: [LICENSE](LICENSE) (GPL-2.0-or-later)


참고해야할 문서
============

아래에서 자신의 역할을 찾아보세요:

* **신규 기여자**: MAGI 코드베이스에 처음 기여하려는 분
* **보안 연구자**: 공격 표면 최소화·정적 분석 정확도에 관심 있는 분
* **DevOps / SRE / 플랫폼 엔지니어**: 컨테이너·단일 목적 서버에 최소 커널을 실제로 적용하려는 분
* **임베디드/커널 엔지니어**: Kconfig 매핑 정확성을 검증하거나 새 아키텍처를 추가하려는 분
* **CI 파이프라인 관리자**: 빌드/배포 파이프라인에 `magi build`를 통합하려는 분
* **AI 코딩 어시스턴트**: 이 저장소를 자동으로 수정/기여하려는 LLM 기반 도구


For Specific Users
===================

신규 기여자
-----------

* 아키텍처 개요: [핵심 아이디어](#핵심-아이디어)
* 코드 위치: 분석기 `src/magi/analyzer/`, 매퍼 `src/magi/mapper/`, 빌더 `src/magi/builder/`, AI 보조 `src/magi/ai_assist/`
* 테스트 실행: `pip install -e ".[dev]" && pytest -q` (47개, 전부 통과해야 함)
* 커밋 전 체크리스트: 새 capability를 추가했다면 `CAPABILITY_MAP`에 대응 항목이 있는지 `tests/test_mapper.py::test_every_capability_has_a_mapping_entry`가 검증합니다.

보안 연구자
-----------

* 위협 모델과 설계 근거: [왜 만들었는가](#왜-만들었는가), [기존 접근과의 차이](#기존-접근과의-차이)
* 정적 분석의 알려진 맹점(동적 디스패치, `dlopen`, 매크로 생성 호출 등): [알려진 한계](#알려진-한계)
* 오탐 필터링 로직(로컬 함수 섀도잉 휴리스틱): [AI 보조 분석](#ai-보조-분석-선택-기능), 코드: `src/magi/ai_assist/heuristic.py`
* Kconfig 매핑 근거(어떤 capability가 왜 어떤 옵션을 켜는지): `src/magi/mapper/kconfig_map.py`의 각 항목 주석, 또는 `magi build --explain`

DevOps / SRE / 플랫폼 엔지니어
-------------------------------

* 빠른 적용: `magi build ./my_service --kernel-src /path/to/linux --arch x86_64 --build`
* 루트 파일시스템 타입 지정: `--root-fs {ext4,xfs,btrfs,vfat,overlay,squashfs}`
* 크로스 컴파일: `--cross-compile <prefix->` (예: `x86_64-linux-musl-`)
* CI 연동을 위한 JSON 출력: `magi analyze ./my_service --json`
* 실서비스 적용 전 반드시 읽을 것: [알려진 한계](#알려진-한계) — 정적 분석은 완전성을 보장하지 않습니다.

임베디드/커널 엔지니어
------------------------

* 새 아키텍처 추가: `src/magi/builder/kernel_build.py`의 `_IMAGE_CANDIDATES`, `_BOOT_TEST_ARCH_CONFIG`에 항목 추가
* Kconfig 매핑 감사: `src/magi/mapper/kconfig_map.py`
* 실제 커널 트리로 검증하는 법: [실제 리눅스 커널 소스로 검증한 기록](#실제-리눅스-커널-소스로-검증한-기록)에 정확히 어떤 명령으로 어떻게 검증했는지 재현 가능하게 적어뒀습니다.

CI 파이프라인 관리자
----------------------

* `magi build ... --kernel-src ... --build --boot-test`는 exit code로 성공/실패를 보고합니다 (부팅 실패 시 non-zero).
* 부팅 테스트는 QEMU가 PATH에 있을 때만 동작하며, 없으면 `ran=False`로 정상적으로 스킵됩니다 — CI에서 QEMU 설치 여부에 따라 자연스럽게 옵트인됩니다.


Communication and Support
==========================

* Issues: 이 저장소의 GitHub Issues
* 만든 사람에게 직접 문의: 아래 [만든 사람](#만든-사람) 참고


---


왜 만들었는가
-------------

일반적인 리눅스 배포판의 커널은 서버, 임베디드, 데스크톱, 다양한 하드웨어 등 거의 모든 사용 사례를 지원하기 위해 방대한 드라이버, 파일시스템, 네트워크 프로토콜, 서브시스템을 함께 포함합니다. 하지만 실제 배포 환경(예: 컨테이너, 임베디드 디바이스, 단일 목적 서버)에서는 이 중 극히 일부 기능만 사용됩니다.

사용하지 않는 코드가 커널에 남아 있으면:

- 공격 표면(attack surface) 증가 — 안 쓰는 기능에 있는 취약점도 여전히 공격 대상이 됩니다.
- 이미지 크기 및 부팅 시간 증가
- 불필요한 리소스 점유

이 프로젝트는 사용자가 배포하려는 프로그램(소스 코드)을 분석해 실제로 어떤 시스템 기능(네트워크, 파일 I/O 등)을 사용하는지 자동으로 판단하고, 그에 맞는 최소 구성으로 커널을 빌드합니다.

기존 접근과의 차이
-------------------

리눅스는 이미 `make localmodconfig`, `make tinyconfig` 같은 최소 설정 도구를 제공합니다. 다만 이들은 공통적으로 "이미 실행 중인 시스템이 실제로 로드한 모듈"을 관찰하는 방식이라, 프로그램을 실행해보기 전에는 적용할 수 없습니다. 학계에서는 정적/동적 분석을 결합해 커널 공격 표면을 줄이는 연구(예: 소스·바이너리 분석으로 syscall 의존성을 추적하는 접근)가 제안된 바 있지만, 개발자가 바로 사용할 수 있는 오픈소스 도구로 공개된 사례는 찾기 어렵습니다.

이 프로젝트는 배포 전 단계(빌드/CI 시점)에서, 실행해보지 않고 소스 코드만으로 필요한 커널 구성을 미리 판단하는 것을 목표로 합니다.

핵심 아이디어
--------------

```
사용자 소스 코드
      │
      ▼
┌─────────────┐
│   분석기     │  코드에서 사용하는 시스템 API 패턴 탐지
│ (Analyzer)  │  (예: socket, accept, fopen, fork ...)
└─────────────┘
      │
      ▼
┌─────────────┐
│  프로파일    │  탐지 결과 → 필요한 Kconfig 옵션 조합으로 매핑
│  매퍼        │
└─────────────┘
      │
      ▼
┌─────────────┐
│  커널 빌더   │  .config 자동 생성 + 빌드 실행
└─────────────┘
      │
      ▼
부팅 가능한 최소 구성 커널 이미지
```

AI 보조 분석 (선택 기능)
--------------------------

규칙 기반 정적 분석은 사전에 정의한 API 패턴만 탐지할 수 있고, 오탐(예: 프로젝트가 `open`이라는 이름의 자체 함수를 정의한 경우)도 발생합니다. 이를 보완하기 위해 단계적인 보조 분석 체인을 둡니다. `magi.ai_assist.Resolver`가 그 확장 지점이며, 실제 구현은 다음 두 단계입니다.

- **기본/1단계 (항상 활성화, 외부 의존성 없음)**: `HeuristicResolver`가 규칙 기반으로 동작합니다 — 예를 들어 매칭된 API 이름과 동일한 이름의 함수가 같은 파일 안에 로컬로 정의되어 있으면(섀도잉) 그 매치를 오탐으로 간주해 제외합니다. 외부 서비스, 네트워크, API 키, 모델 파일이 전혀 필요 없고, 이 프로젝트의 핵심 기능은 전적으로 이 경로로 재현 가능합니다. "로컬 LLM"이 아니라 순수 규칙 기반 휴리스틱임을 명시합니다.
- **2단계 (선택, 사용자가 직접 구성)**: `LocalLLMResolver`는 `llama-cpp-python` + 사용자가 지정한 GGUF 모델 파일(`--model-path`)이 실제로 존재할 때만 활성화되는 플러그인입니다. 모델 가중치는 이 저장소에 포함되어 있지 않습니다(수백 MB~수 GB에 달하고 하드웨어 요구사항이 프로젝트마다 다르기 때문). 모델이나 의존성이 없으면 `is_available()`이 False를 반환하고 자동으로 1단계 휴리스틱만 사용됩니다.

즉 "AI 보조 서버"가 별도로 구동되는 구조가 아니라, 분석 파이프라인 내 in-process 필터 체인입니다. 소스 코드가 프로세스 밖으로 전송되는 경로 자체가 없으므로, 이 프로젝트가 지향하는 보안 원칙(공격 표면 최소화)과도 일관성을 가집니다.

개발 단계 (Roadmap)
---------------------

정직한 스코프 관리를 위해 3단계로 나누어 진행합니다. 각 단계는 리스크와 구현 난이도가 크게 다르며, 낮은 단계부터 안정적으로 완성하는 것을 우선합니다.

### Phase 1 — 빌드 시점 최소화 (Kconfig 자동화)

목표: 공격 표면 축소, 이미지 크기·부팅 시간 단축

- [x] 소스 코드 정적 분석기: 네트워크/파일 I/O/스레딩 등 API 사용 패턴 탐지
- [x] 탐지 결과 → Kconfig 옵션 매핑 테이블
- [x] `.config` 자동 생성 및 기존 리눅스 빌드 도구(`merge_config.sh` 등)와 연동
- [x] 실제 부팅 가능한 커스텀 커널 이미지 생성 파이프라인 (`--build --boot-test`) — 실제 Linux 6.6.79로 끝까지 검증 완료, 아래 참고
- [ ] 기본 defconfig 대비 이미지 크기 / 빌드 시간 / 활성화된 Kconfig 옵션 수 비교

세부 완료 현황과 알려진 한계는 아래 [개발 상태](#개발-상태) / [알려진 한계](#알려진-한계) 절을 참고하세요.

### Phase 2 — 런타임 파라미터 자동 튜닝

목표: 목적에 맞는 커널 동작 방식 최적화 (커널 소스 자체는 변경하지 않음)

- [ ] 워크로드 종류에 맞는 스케줄링 정책/파라미터 자동 선택
- [ ] 관련 sysctl 값 자동 설정
- [ ] Phase 1 대비 실제 성능 지표(지연시간, 처리량 등) 비교

### Phase 3 — 워크로드 특화 스케줄링 실험 (장기 비전)

목표: sched_ext(eBPF 기반 커스텀 스케줄러) 등을 활용한 워크로드 전용 정책 실험

- [ ] eBPF 기반 커스텀 스케줄링 정책 프로토타입
- [ ] 특정 워크로드(예: 네트워크 서버)에 대한 정책 비교 실험

Phase 3는 현재 시점에서 완성을 약속하는 항목이 아니라 방향성입니다. 커널 스케줄러 핵심 로직 자체를 새로 설계하는 것은 검증에 오랜 시간이 필요한 작업이라, 이번 프로젝트에서는 리눅스가 이미 제공하는 확장 지점(sched_ext 등)을 활용하는 수준까지를 목표로 합니다.

설치
-----

```bash
pip install -e .          # 개발 모드 설치 (src/ 레이아웃)
pip install -e ".[dev]"   # + pytest
```

의존성은 순수 표준 라이브러리뿐입니다 (`--no-ai`를 쓰지 않아도 규칙 기반 경로는 항상 외부 패키지 없이 동작). 선택적으로 로컬 LLM 보조를 쓰려면 `pip install -e ".[llm]"`로 `llama-cpp-python`을 추가 설치하고 `--model-path`에 GGUF 모델 경로를 지정하세요.

실제 커널을 빌드하려면(`--build`) 별도로 리눅스 커널 빌드 요구사항(`make`, `gcc`/크로스 툴체인, `bc`, `bison`, `flex`, `libssl-dev`, `libelf-dev`)이 필요합니다 — 가장 안정적인 방법은 리눅스 환경(또는 Docker 컨테이너) 안에서 빌드하는 것입니다. macOS 호스트에서 직접 빌드하는 것은 리눅스 커널 빌드 시스템의 호스트 도구가 macOS와 근본적으로 맞지 않는 지점이 있어 권장하지 않습니다 — 자세한 내용은 [실제 리눅스 커널 소스로 검증한 기록](#실제-리눅스-커널-소스로-검증한-기록)을 참고하세요.

사용법
-------

```bash
# 소스 코드가 실제로 쓰는 커널 기능 확인
magi analyze ./my_project

# JSON으로 출력 (CI 연동용)
magi analyze ./my_project --json

# Kconfig 조각(fragment) 생성만
magi build ./my_project --out magi.config

# 왜 이 옵션들이 켜졌는지 설명까지 보기
magi build ./my_project --out magi.config --explain

# 실제 커널 소스 트리에 대해 .config까지 생성
magi build ./my_project --kernel-src /path/to/linux --arch x86_64

# 크로스 컴파일 (예: macOS에서 리눅스 커널을 대상으로)
magi build ./my_project --kernel-src /path/to/linux --arch x86_64 --cross-compile x86_64-linux-musl-

# .config 생성 + 실제 빌드 + QEMU 부팅 스모크테스트까지
magi build ./my_project --kernel-src /path/to/linux --build --boot-test
```

`magi build`는 항상 `allnoconfig`(가장 작은 베이스라인) → MAGI가 생성한 fragment를 `scripts/kconfig/merge_config.sh -m`으로 병합 → `olddefconfig`(의존성 해석) 순서로 실제 커널 빌드 도구를 그대로 호출합니다. Kconfig 의존성 해석 자체를 재구현하지 않고 커널이 이미 제공하는 정본 구현에 위임하는 것이 의도적인 설계입니다.

개발 상태
----------

Phase 1 핵심 파이프라인(정적 분석기 → Kconfig 매퍼 → fragment/.config 생성기 → 빌드/부팅 오케스트레이션)이 동작하며, 47개의 자동화 테스트로 검증되어 있습니다(`pytest -q`). 아래 "실제 리눅스 커널 소스로 검증한 기록"에 정리했듯, 실제 Linux 6.6.79 소스로 컴파일부터 QEMU 부팅까지 MAGI 자신의 CLI로 완주했습니다.

- [x] 소스 코드 정적 분석기 (C: 렉시컬 스캔, Python: `ast` 기반 — import alias 추적 포함)
- [x] 탐지 결과 → Kconfig 옵션 매핑 테이블 (모든 capability에 대해 매핑 완전성 테스트로 보증)
- [x] `.config` 자동 생성 및 `merge_config.sh` 연동
- [x] 빌드 파이프라인 자동화 (`magi build --kernel-src ... --build`), `--cross-compile` 지원
- [x] QEMU 부팅 스모크테스트 (`--boot-test`, best-effort — 커널이 실제로 실행을 시작했는지 부팅 배너로 확인)
- [x] 규칙 기반 정적 분석의 한계를 보완하는 AI 보조 1단계(로컬 함수 섀도잉 휴리스틱, 외부 의존성 없음) — 항상 활성화
- [ ] AI 보조 2단계(로컬 LLM) — 플러그인 인터페이스는 구현 완료, 모델 가중치는 번들하지 않음 (`--model-path`로 사용자가 직접 지정)
- [ ] 기본 defconfig 대비 이미지 크기 / 빌드 시간 / 활성화된 Kconfig 옵션 수 비교 데모

### 실제 리눅스 커널 소스로 검증한 기록

fixture 기반 통합 테스트에 더해, 실제 [Linux 6.6.79](https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.6.79.tar.xz) 소스 트리를 내려받아 MAGI가 생성한 fragment를 그 트리의 진짜 `scripts/kconfig/merge_config.sh`에 직접 통과시켜 검증했습니다. 이 과정에서 fixture만으로는 드러나지 않던 실제 버그 두 개를 발견해 고쳤습니다.

1. **fragment 포맷 버그 (수정 완료)**: 초기 버전은 각 옵션 위에 `# CONFIG_NET: reason` 형태의 설명 주석을 넣었는데, 실제 `merge_config.sh`는 옵션 값을 `grep -w $CFG file`로 찾습니다 — 주석 안에 옵션 이름이 그대로 들어 있으면 이 grep이 주석 줄과 실제 줄을 동시에 매치해 병합이 조용히 깨집니다. `render_fragment()`에서 주석을 완전히 제거하고, 이유 설명은 별도 함수 `render_explanation()` / `magi build --explain`으로 분리했습니다. 회귀 테스트로 고정했습니다.
2. **macOS 호스트 툴체인 비호환성 (감지 후 명확한 에러로 전환)**: `merge_config.sh`는 `sed -i` / `cp -T` 같은 GNU 전용 문법을 씁니다. macOS 시스템 `sed`/`cp`는 BSD 버전이라 `sed -i`가 스크립트를 백업 접미사로 오인해 병합이 아무 경고 없이 실패합니다. `check_host_toolchain()`을 추가해 이 상황을 미리 감지하고 (`brew install gnu-sed coreutils` 안내와 함께) 즉시 실패하도록 만들었습니다.

이 두 수정을 반영한 뒤, 실제 커널 트리에서 `allnoconfig` → MAGI fragment 병합 → `olddefconfig`가 전부 성공했고, 결과 `.config`에 MAGI가 의도한 옵션만 정확히 반영됨을 확인했습니다 (예: `network_inet`+`filesystem_io`+`ipc_shared_mmap` 소스에 대해 `CONFIG_NET`/`CONFIG_INET`/`CONFIG_EXT4_FS`/`CONFIG_BLOCK`/`CONFIG_SHMEM`은 `=y`, `CONFIG_SOUND`/`CONFIG_USB_SUPPORT`/`CONFIG_BT`는 미설정).

첫 시도에서는 macOS 호스트 자체에서 네이티브 크로스 컴파일(Homebrew `musl-cross`)로 실제 바이너리까지 완주하려다, 리눅스 커널 빌드 시스템의 호스트 도구(x86_64는 `objtool`이 리눅스 전용 uapi 헤더를 요구, 아키텍처 불문 `scripts/mod/file2alias.c`가 macOS SDK의 `uuid_t`와 이름 충돌)가 macOS 호스트와 근본적으로 맞지 않는 지점에서 막혔습니다. 이 시점엔 Docker Desktop도 VM 백엔드가 응답하지 않는 상태였습니다.

**이후 Docker Desktop을 강제 종료 후 재시작하니 정상 동작했고, 진짜 Linux 컨테이너(Ubuntu 22.04)에서 `magi build --kernel-src ... --arch arm64 --build --boot-test`를 MAGI CLI로 직접 실행해 끝까지 완주했습니다.**

- 실제 Linux 6.6.79 소스에 대해 `make ARCH=arm64 Image`가 컨테이너 안에서 완주 — `arch/arm64/boot/Image` (6,807,560 bytes)가 실제로 생성됨 (`file`로 확인: `Linux kernel ARM64 boot executable Image, little-endian, 4K pages`)
- `qemu-system-aarch64 -M virt`로 부팅 → 진짜 `Linux version 6.6.79 (...)` 배너부터 네트워크 스택 초기화(`NET: Registered PF_INET protocol family`, TCP/UDP 해시 테이블 구성 — 소스가 실제로 쓰는 `network_inet`과 정확히 대응)까지 전부 출력됨. 루트 파일시스템을 주지 않았으므로 마지막엔 의도한 대로 `VFS: Unable to mount root fs on unknown-block(0,0)` 커널 패닉으로 끝남 (이는 실패가 아니라 예상된 정상 동작 — MAGI의 `boot_test()`는 정확히 이 지점, 즉 커널이 실행을 시작했다는 증거(부팅 배너)만 확인하도록 설계되어 있음).
- `magi build ... --boot-test`의 최종 출력: `boot test: PASS (kernel banner observed under QEMU)`, `CLI_EXIT_CODE=0`

이 실제 부팅 테스트 도중 **세 번째, 네 번째 진짜 버그**를 더 찾아 고쳤습니다 (fixture 테스트만으로는 절대 드러날 수 없는 종류의 버그들입니다):

3. **`BASE_OPTIONS`에 콘솔/UART 드라이버가 빠져 있었음**: 부팅 로그를 직접 봤더니 커널은 완전히 정상 실행 중인데(`-d int`로 확인한 실제 PSCI/인터럽트 트레이스) 화면에 아무것도 안 찍혔습니다. 원인은 `CONFIG_TTY`/`CONFIG_VT`/`CONFIG_VT_CONSOLE`은 가상 터미널 계층일 뿐, 실제 UART 드라이버가 아니었다는 것 — `console=ttyAMA0`(또는 x86의 `ttyS0`)를 받아줄 디바이스가 아예 없어 모든 printk가 허공으로 사라지고 있었습니다. `CONFIG_SERIAL_8250`/`_CONSOLE`(x86)과 `CONFIG_SERIAL_AMBA_PL011`/`_CONSOLE`(arm/arm64, QEMU virt 보드)을 `BASE_OPTIONS`에 추가했습니다 — 해당 아키텍처에 없는 옵션은 Kconfig가 조용히 무시하므로 두 계열을 동시에 넣어도 안전합니다.
4. **`boot_test()`가 애초에 arm64/arm을 지원하지 않았음**: `--arch arm64 --boot-test`를 실제로 호출해보니 `qemu-system-aarch64`로의 매핑이 아예 없었고(`x86_64`/`i386`만 있었음), 게다가 `console=ttyS0`(x86 전용)를 무조건 하드코딩하고 있었으며 `-M`(머신 타입) 인자도 없었습니다 — arm64는 애초에 부팅조차 불가능한 상태였습니다. 아키텍처별 QEMU 설정 테이블(`qemu_bin`/`console`/`extra_args`)로 재작성하고, `-nographic`을 `-display none -serial stdio -monitor none`으로 바꿔 실제로 stdout에 시리얼 로그가 잡히는 것까지 확인했습니다. 타임아웃 경로에서 `TimeoutExpired.stdout`이 str이 아니라 bytes로 오는 경우를 방어하지 않아 크래시하던 것도 같이 고쳤습니다.

정리하면: **정식 출시라 부를 만한 검증을 실제로 완료했습니다.** Kconfig 생성·병합·해석부터, 진짜 Linux 6.6.79 소스의 실제 컴파일(`vmlinux`/`Image` 바이너리 산출), 진짜 QEMU 부팅(커널 배너 확인)까지 MAGI 자신의 CLI(`magi build --build --boot-test`)로 전부 통과했습니다. 이 과정에서 발견한 버그 4개는 전부 고쳤고 회귀 테스트로 고정했습니다 (47개 테스트 전부 통과).

알려진 한계
------------

- **정적 분석의 근본적 한계**: 동적 디스패치, 리플렉션, `dlopen`/`ctypes`로 로드되는 코드, 매크로로 생성된 호출 등은 탐지되지 않습니다. 놓친 기능이 있으면 커널이 부팅 후 실패할 수 있습니다 — MAGI는 "이 실행 경로가 확실히 쓰는 기능"의 하한선을 제공하는 도구이지, 완전성을 보장하지 않습니다.
- C 분석기는 전체 파서가 아니라 렉시컬 스캐너입니다. 문자열/주석은 제거하지만 스코프는 이해하지 못하므로(예: 지역 변수 `int socket = 5;`는 오탐이 될 수 있음), AI 보조 단계가 가장 흔한 오탐(동일 이름의 지역 함수 정의) 하나를 필터링합니다.
- Kconfig 매핑 테이블은 수동으로 큐레이션되었으며 커널 버전에 따라 옵션 이름이 달라질 수 있습니다 (예: 매우 오래된/최신 트리).

라이선스
---------

GPL-2.0-or-later ([LICENSE](LICENSE) 참고). 리눅스 커널 자체도 GPL-2.0이며, 본 프로젝트가 생성하는 산출물(Kconfig fragment, `.config`)은 커널 설정 데이터일 뿐 커널 소스를 포함하지 않으므로 별도 라이선스 고지가 필요하지 않습니다.

만든 사람
----------

chodaQ— [ChodOS](https://github.com/chodaQ/chodOS) 개발 및 리눅스 커널 staging tree 기여 경험을 바탕으로 시작한 프로젝트입니다.
