import socket       # 네트워크 통신(TCP/IP)을 하기 위해 추가
import struct       # struct 는 4개의 바이트 덩어리를 숫자(정수)로 변환하는 역할, 유니티가 보낸 데이터릐 길이 정보를 읽는 데 사용
import time        

HOST = "127.0.0.1"  # 로컬 주소로 설정
PORT = 10000        # 포트 번호 설절

def extract_joint_data(data):
    # 수신된 바이트 데이터에서
    # 1. 읽을 수 있는 텍스트(토픽 이름 등)와
    # 2. 관절 각도로 추정되는 실수(float64) 데이터를 분리하여 추출

    # 1. 텍스트 추출 (깨진 문자는 무시하고 읽을 수 있는 것만 추출)
    text_part = data.decode("utf-8", errors="ignore").strip()
    # 공백이나 특수문자 정리
    clean_text = ''.join(char for char in text_part if char.isprintable())

    # 2. 숫자(Double, 8byte) 추출 시도
    # 데이터 스트림 내에서 8바이트씩 슬라이딩 하며 유효한 숫자 범위인지 체크
    found_numbers = []

    # 데이터 길이가 8바이트 이상일 때만 탐색(Unity 에서 double 로 전달해서 8바이트)
    if len(data) >= 8:
        for i in range(len(data) - 7):
            chunk = data[i:i+8]
            try:
                # "<d": 리틀 엔디안 double (8바이트 실수)
                value = struct.unpack("<d", chunk)[0]
                
                # 필터링, 로봇 관절 각도는 보통 -6.28(-2pi) ~ 6.28(2pi) 범위 내에 있음
                # 데이터 오인식을 막기 위해 범위 제한 (-10 ~ 10, 로봇 관절 각도를 모두 커버할 수 있게 지정)
                # 0.000000 으로 너무 작은 수(노이지)가 아닌 지 확인
                if -10.0 <= value <= 10.0:
                    # 0.0 인 경우에도 포함되어야 하기 때문에 아주 큰 수나 NaN 값만 거름
                    found_numbers.append(value)
            except:
                continue

    return clean_text, found_numbers

def start_server():
    print(f"Python 서버 대기 중... ({HOST}:{PORT})")
    # 소켓 생성
    # AF_INET: IPv4 주소 체계를 사용하겠다는 의미
    # SOCK_STREAM: TCP 프로토콜을 사용 (데이터가 끊기지 않고 순서대로 도착)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # server.setsockopt: 소켓에 옵션을 설정하는 함수
    # socket.SOL_SOCKET: 옵션을 적용할 대상 츨(Level)을 지정
    # 네트워크는 여러 층(프로토콜)으로 되어 있음 (TCP, IP 등)
    # SOL_SOCKET은 특정 프로토콜(TCP/IP)이 아니라, 소켓 장치 그 차체에 설정을 지정하겠다는 의미
    # socket.SO_REUSEADDR: 소켓의 주소 재사용 옵션을 지정
    # 서버가 강제로 종료되거나 close()를 해도, 운영체제는 네트워크상에서 지연되는 패킷에 대비하여 해당 포트를 
    # 잠시동안(1, 2분) 대기 상태(TIME_WAIT)로 남겨두고 락을 설정
    # 이때 서버를 더시 켜려로 할때 운영체제는 포트가 중복되는 것을 방지 하기 위해 Address already in use 에러를 전달
    # socket.SO_REUSEADDR 을 지정하면 포트가 대기 상태(TIME_WAIT)여도 무시하고 다시 지정(Reuse)하는 옵션
    # 마지막 매개변수 1: True 로 지정한 옵션을 활성화 한다는 뜻, 0 은 비활성화
    # 개발 및 테스트 단계에서 수시로 서버를 온오프 할때 포트의 잠김이 풀리는 것을 기다리는 부분이 발생하지 않게 지정
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # bind: IP와 PORT를 등록
    server.bind((HOST, PORT))

    # listen(1): 클라이언트(Unity)의 접속을 대기, 1은 동시에 접속할 클라이언트의 숫자
    server.listen(1)

    # erver.accept(): 클라이언트(Unity)가 접속할 때 까지 계속 대기
    # 클라이언트(Unity)가 접속 할 시 connect(통신용 소켓), address(클라이언트(Unity) 주소)변수애 값을 반환 
    connect, address = server.accept()
    print(f"Unity 연결됨: {address}")

    # try/catch : 예외 처리 구문
    try:
        # 연결 종료 까지 계속 진행
        while True:
            # 1. 데이터 수신 (데이터 길이 넉넉하게 4k)
            data = connect.recv(4096)

            # 만약 Unity 에서 전달한 데이터가 없다면, 연결이 종료되었기 때문에 반복문 종료
            if not data:
                break

            # 데이터 파싱
            text_info, angles = extract_joint_data(data)

            # 결과 출력
            # 숫자가 발견되었을 경우 처리
            # 일정 수치 이상 변화 되었을 경우 처리
            #if len(angles) > 0:
            if any(abs(a) > 0.0001 for a in angles):
                # 소수점 4자리로 포맷팅
                formatted_angles = [f"{a:.4f}" for a in angles]

                print(f"패킷 수신 ({len(data)} bytes)")

                if "joint_state" in text_info:
                    print(f"[토픽] joint_state 감지됨")

                print(f"[데이터] 변환된 각도: {formatted_angles}")

                # 추후에 로봇 제어 구문 추가

            # 숫자는 없지만 텍스트 정보가 있는 경우(연결 초기 정보 등)
            elif len(text_info) > 5:
                print(f"[정보] 텍스트 메시지: {text_info}")

    except ConnectionRefusedError:
        print("연결 실패")
    except Exception as e:
        print(f"종료: {e}")
    finally:
        # try/catch 구문중 어디로 진행 하더라고 마지막엔 finally 구문 실행
        # 연결 종료 철리
        connect.close()
        server.close()

if __name__ == "__main__":
    start_server()