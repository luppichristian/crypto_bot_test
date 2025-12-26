from config import *
import paramiko

def download_file_from_server(remote_path, local_path):
    try:
        transport = paramiko.Transport((server_config["HOSTNAME"], server_config["PORT"]))
        transport.connect(username=server_config["USERNAME"], password=server_config["PASSWORD"])
        sftp = paramiko.SFTPClient.from_transport(transport)
        remote_file_path = remote_path.format(TRADING_STATE_FILE=TRADING_STATE_FILE)
        local_file_path = local_path.format(TRADING_STATE_FILE=TRADING_STATE_FILE)
        sftp.get(remote_file_path, local_file_path)
        sftp.close()
        transport.close()
    except Exception as e:
        print(f"Failed to download file from server: {e}")

if __name__ == "__main__":
    load_server_config()
    download_file_from_server(f"/root/crypto-bot/{TRADING_STATE_FILE}", f"{TRADING_STATE_FILE}")
    download_file_from_server(f"/root/crypto-bot/{LOGGING_FILE}", f"{LOGGING_FILE}")