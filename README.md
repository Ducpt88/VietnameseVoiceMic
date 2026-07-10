# Vietnamese Voice Mic

Ung dung Windows chay nen de nhap tieng Viet bang giong noi vao o chat/input.

## Tinh nang chinh

- Kich hoat bang `Alt + click chuot trai` vao dung o muon nhap.
- Khoa cua so va vi tri ban dau, sau khi nhan dien se dan lai dung vi tri do.
- Nhan dien tieng Viet bang Google Speech Recognition, co confidence trong log/HUD khi Google tra ve.
- VAD bang WebRTC/RMS de biet khi nao dang noi va khi nao da ngung.
- Toi uu cho doan noi dai: cat chunk tai vung am luong thap, gui chunk song song, ghep bo trung lap.
- HUD/vong tron hien trang thai: dang nghe, dang nhan dien, da co text.
- Bao ve dan nham: neu cua so target da dong thi bo qua dan.
- Recovery: transcript moi nhat duoc giu tren clipboard, luu vao `voice-last.txt`,
  lich su luu vao `voice-transcripts.jsonl`, audio gan nhat luu vao `voice-last.wav`.
- Co the build ban Windows `.exe`, tao zip release va manifest update.
- Auto-update doc manifest tu GitHub Release latest.
- Du lieu ca nhan/context hoc rieng luu local va khong dua len GitHub.

## Cach dung nhanh

1. Chay `Start Vietnamese Voice Mic.cmd`.
2. Giu `Alt` va click chuot trai vao o chat/input muon nhap.
3. Khi vong tron hien `DANG NGHE`, noi noi dung can nhap.
4. Khi ban ngung noi, app doi sang `DANG NHAN DIEN`.
5. Khi co ket qua, app hien preview va tu dan vao dung vi tri da `Alt + click`.
6. Sau khi app nhan dien, ban co the bam `Ctrl+V` de dan lai transcript moi nhat neu can.
7. Khi dang nghe, bam `Esc` de dung va xu ly phan audio da thu.

## Cuu lai noi dung vua noi

Neu app cat cau, dan loi, hoac ban doi cua so lam target khong con dung:

- Bam `Ctrl+V` de dan lai transcript moi nhat vi app giu no tren clipboard.
- Mo `voice-last.txt` de xem transcript moi nhat.
- Mo `voice-transcripts.jsonl` de xem lich su cac lan nhan dien.
- File `voice-last.wav` giu audio gan nhat, huu ich khi can kiem tra lai am thanh da thu.

Nhung file recovery nay nam tren may cua ban va da duoc dua vao `.gitignore`, khong day len GitHub.

## Cau hinh mic

File cau hinh:

```text
voice-mic-settings.json
```

Vi du:

```json
{
  "preferred_microphone": "BKD-11 Pro Audio",
  "microphone_name_hints": [
    "BKD-11 Pro Audio",
    "USB Audio Device",
    "Microphone",
    "Headset"
  ],
  "enable_particle_effect": true,
  "enable_context_memory": true
}
```

Neu muon app tu chon mic theo danh sach goi y, dat:

```json
"preferred_microphone": ""
```

## Chay tu source

Yeu cau:

- Windows 10/11
- Python 3.10 tro len
- Microphone hoat dong
- Internet de dung Google Speech Recognition

Cai thu vien:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Chay app:

```powershell
python .\voice_mic_icon.py
```

Hoac:

```text
Start Vietnamese Voice Mic.cmd
```

## Cai tu chay cung Windows

Chay PowerShell tai thu muc project:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-startup.ps1
```

Go auto-start:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-startup.ps1
```

## Build ban phat hanh

Chay:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Ket qua:

```text
dist\VietnameseVoiceMic\VietnameseVoiceMic.exe
releases\VietnameseVoiceMic-windows.zip
releases\version.json
```

Gui thu muc nay cho nguoi khac:

```text
dist\VietnameseVoiceMic
```

Hoac upload zip trong `releases` len GitHub Release.

## Day len GitHub

Kiem tra thay doi:

```powershell
git status
git diff --stat
```

Commit:

```powershell
git add .
git commit -m "Improve Vietnamese Voice Mic dictation"
```

Push len GitHub:

```powershell
git push origin main
```

## Cap nhat ban moi

Build script tao `releases\version.json` gom:

- `version`
- `zip_url`
- `sha256`
- `notes`
- `release_url`

Auto-update mac dinh doc manifest tai:

```text
https://github.com/Ducpt88/VietnameseVoiceMic/releases/latest/download/version.json
```

Khi tao ban moi, chay `build.ps1`, sau do upload 2 file nay len GitHub Release:

```text
releases\VietnameseVoiceMic-windows.zip
releases\version.json
```

## Xu ly loi thuong gap

- Khong nhan giong: kiem tra mic trong Windows va `preferred_microphone`.
- Bi cat cau som: tang `WEBRTC_VOICE_END_SECONDS` va `RMS_VOICE_END_SECONDS` trong `voice_mic_icon.py`.
- Nhan sai nhieu: noi gan mic hon, giam tieng nen, hoac them tu khoa vao `speech_context_terms`.
- Khong dan dung cho: hay `Alt + click` dung vao o input truoc khi noi.
- App khong bat: phai giu `Alt` trong luc click chuot trai vao o input.

## File quan trong

- `voice_mic_icon.py`: code app chinh.
- `voice-mic-settings.json`: cau hinh mic, context, update.
- `voice-mic-settings.local.json`: cau hinh rieng cua tung may, khong dua len GitHub.
- `voice-context.json`: bo nho public mac dinh, khong chua transcript ca nhan.
- `voice-context.local.json`: bo nho hoc rieng cua tung may, khong dua len GitHub.
- `voice-last.txt`: transcript moi nhat de cuu lai khi can.
- `voice-transcripts.jsonl`: lich su transcript tren may local.
- `voice-last.wav`: audio gan nhat da thu tren may local.
- `Start Vietnamese Voice Mic.cmd`: chay app tu source.
- `Start-VietnameseVoiceMic.ps1`: restart app va dam bao chi con mot instance.
- `build.ps1`: build exe, zip release va manifest.
- `updater.ps1`: helper cap nhat ban moi.
- `install-startup.ps1`: cai auto-start cung Windows.
- `uninstall-startup.ps1`: go auto-start.
