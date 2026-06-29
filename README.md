# Vietnamese Voice Mic

Vietnamese Voice Mic là ứng dụng Windows chạy nền để nhập tiếng Việt bằng giọng nói vào ô chat/input.

## Tính năng

- Chạy nền, không hiện nút mic nổi 24/24.
- Chỉ bật khi giữ `Alt` và click chuột trái vào ô chat/input.
- Tự nghe một câu, khi bạn ngừng nói thì tự xử lý.
- Dán text một lần vào đúng vị trí đã `Alt + click` ban đầu.
- Ưu tiên Google Speech Recognition tiếng Việt để nhận diện chính xác hơn.
- Có thể cài tự chạy cùng Windows.

## Cách dùng nhanh

1. Chạy `Start Vietnamese Voice Mic.cmd`.
2. Giữ `Alt` và click chuột trái vào ô chat/input muốn nhập.
3. Khi thấy `Hãy nói đi Sếp ơi!`, hãy nói câu cần nhập.
4. Khi app hiện `Tèn tén tén ten....!`, app đang xử lý và sẽ tự dán text.
5. Khi đang nghe, bấm `Esc` để dừng nhanh.

## Cài tự chạy cùng Windows

Chạy PowerShell tại thư mục project:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-startup.ps1
```

Từ lần sau mở máy hoặc đăng nhập Windows, app sẽ tự chạy nền.

Muốn gỡ auto-start:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-startup.ps1
```

## Cấu hình mic

File cấu hình nằm ở:

```text
voice-mic-settings.json
```

Ví dụ muốn ưu tiên một mic cụ thể:

```json
{
  "preferred_microphone": "BKD-11 Pro Audio",
  "microphone_name_hints": [
    "BKD-11 Pro Audio",
    "USB Audio Device",
    "Microphone",
    "Headset"
  ]
}
```

Nếu để `"preferred_microphone": ""`, app sẽ tự chọn mic đầu tiên khớp `microphone_name_hints`.

## Chạy từ source code

Yêu cầu:

- Windows 10/11
- Python 3.10 trở lên
- Microphone hoạt động
- Internet nếu muốn dùng Google Speech Recognition

Cài thư viện:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Chạy app:

```powershell
python .\voice_mic_icon.py
```

Hoặc chạy file:

```text
Start Vietnamese Voice Mic.cmd
```

## Đóng gói thành app gửi cho người khác

Chạy:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Sau khi build xong, app nằm tại:

```text
dist\VietnameseVoiceMic\VietnameseVoiceMic.exe
```

Gửi nguyên thư mục này cho người khác:

```text
dist\VietnameseVoiceMic
```

Người nhận chỉ cần mở:

```text
VietnameseVoiceMic.exe
```

Nếu muốn app tự chạy cùng Windows trên máy người nhận, chạy trong thư mục app đã build:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-startup.ps1
```

## Bản offline Whisper tùy chọn

Mặc định app dùng Google trước để nhận diện tiếng Việt tốt hơn và nhẹ hơn.

Nếu muốn cài thêm Whisper offline:

```powershell
pip install -r requirements-whisper.txt
```

Lưu ý: Whisper/Torch rất nặng, build ra file lớn và máy yếu có thể chạy chậm.

## File quan trọng

- `voice_mic_icon.py`: code app chính.
- `voice-mic-settings.json`: cấu hình mic.
- `Start Vietnamese Voice Mic.cmd`: chạy app từ source.
- `build.ps1`: đóng gói app bằng PyInstaller.
- `install-startup.ps1`: cài auto-start cùng Windows.
- `uninstall-startup.ps1`: gỡ auto-start.

## Xử lý lỗi thường gặp

- Không nhận giọng: kiểm tra mic trong Windows, rồi chỉnh `preferred_microphone`.
- Nhận sai nhiều: nói gần mic hơn, giảm tiếng nền, hoặc thử mic khác.
- App không tự bật: phải giữ `Alt` trong lúc click chuột trái vào ô input.
- Không dán đúng chỗ: hãy `Alt + click` đúng vào vùng nhập text trước khi nói.
