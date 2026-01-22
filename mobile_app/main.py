import flet as ft
import asyncio
import urllib.request
import urllib.error
import json
import os
import uuid

# QR Scanning dependencies
try:
    from PIL import Image
    from pyzbar.pyzbar import decode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Global state to hold connection details
APP_STATE = {
    "server_url": "",
    "token": ""
}

CURRENT_VERSION = "1.0.0"
GITHUB_REPO = "qztq/LeprendiX"
GITHUB_TOKEN = "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"


async def main(page: ft.Page):
    page.title = "LeprendiX Mobile"
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 20

    # Initialize FilePickers in overlay once
    qr_picker = ft.FilePicker()
    file_picker = ft.FilePicker()
    page.overlay.extend([qr_picker, file_picker])

    # Connection View
    async def show_connect_view():
        page.clean()
        
        ip_field = ft.TextField(
            label="Server IP:Port",
            hint_text="e.g. 192.168.1.5:5000"
        )
        token_field = ft.TextField(
            label="Token",
            hint_text="Session Token",
            password=True,
            can_reveal_password=True
        )
        status_text = ft.Text("", color="red", size=14)

        async def on_qr_result(e: ft.FilePickerResultEvent):
            if e.files:
                if not QR_AVAILABLE:
                    status_text.value = "QR libraries (PIL/pyzbar) not installed"
                    status_text.color = "red"
                    await page.update_async()
                    return
                
                try:
                    fpath = e.files[0].path
                    decoded = decode(Image.open(fpath))
                    if decoded:
                        data = decoded[0].data.decode('utf-8')
                        # Format: IP:PORT|TOKEN
                        if "|" in data:
                            ip, token = data.split("|", 1)
                            ip_field.value = ip
                            token_field.value = token
                            status_text.value = "Scanned successfully!"
                            status_text.color = "green"
                        else:
                            status_text.value = "Invalid QR format"
                    else:
                        status_text.value = "No QR code found"
                except Exception as ex:
                    status_text.value = f"Scan error: {ex}"
                await page.update_async()

        qr_picker.on_result = on_qr_result

        async def on_connect_click(e):
            if not ip_field.value or not token_field.value:
                status_text.value = "Please enter IP and Token from Desktop"
                status_text.color = "red"
                await page.update_async()
                return
            
            status_text.value = "Connecting..."
            status_text.color = "yellow"
            await page.update_async()
            
            # Construct URL
            base_url = f"http://{ip_field.value}"
            try:
                # Verify connection
                verify_url = f"{base_url}/verify"
                data = json.dumps({"token": token_field.value}).encode("utf-8")
                
                def do_verify():
                    req = urllib.request.Request(
                        verify_url,
                        data=data,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        return resp.status == 200
                
                success = await asyncio.to_thread(do_verify)
                
                if success:
                    APP_STATE["server_url"] = base_url
                    APP_STATE["token"] = token_field.value
                    await show_upload_view()
            except urllib.error.HTTPError:
                status_text.value = "Invalid Token or Server Error"
                status_text.color = "red"
            except Exception as ex:
                status_text.value = f"Connection Failed: {str(ex)[:40]}"
                status_text.color = "red"
            await page.update_async()

        page.appbar = ft.AppBar(
            title=ft.Text("Connect to LeprendiX"),
            bgcolor="surfaceVariant"
        )
        
        # Always show both buttons, they'll be disabled/hidden if needed
        async def scan_qr_click(e):
            await qr_picker.pick_files(file_type=ft.FilePickerFileType.IMAGE)

        page.add(
            ip_field,
            token_field,
            ft.Row(
                [
                    ft.Button("Connect", on_click=on_connect_click, expand=True),
                    ft.Button("Scan QR", on_click=scan_qr_click)
                ],
                spacing=10
            ),
            status_text
        )

    # Upload View
    async def show_upload_view():
        page.clean()
        
        status_text = ft.Text("Waiting for request...", size=16, color="blue")
        preview_image = ft.Image(src="", visible=False, height=300, fit=ft.ImageFit.CONTAIN)
        
        confirm_row = ft.Row(
            visible=False,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20
        )
        
        async def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.files:
                path = e.files[0].path
                preview_image.src = path
                preview_image.visible = True
                confirm_row.visible = True
                scan_button.visible = False
                status_text.value = "Review Image"
                status_text.color = "blue"
                await page.update_async()

        file_picker.on_result = on_dialog_result

        async def on_scan_click(e):
            await file_picker.pick_files(file_type=ft.FilePickerFileType.IMAGE)

        scan_button = ft.Button("Take Photo / Select Image", on_click=on_scan_click)
        
        async def upload_file(filepath):
            status_text.value = "Uploading..."
            status_text.color = "yellow"
            await page.update_async()
            
            try:
                url = f"{APP_STATE['server_url']}/upload"
                
                # Multipart upload using urllib
                boundary = uuid.uuid4().hex
                headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
                body = b""
                
                # Token field
                body += f"--{boundary}\r\n".encode()
                body += f'Content-Disposition: form-data; name="token"\r\n\r\n'.encode()
                body += f"{APP_STATE['token']}\r\n".encode()
                
                # File field
                filename = os.path.basename(filepath)
                body += f"--{boundary}\r\n".encode()
                body += f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode()
                body += b"Content-Type: application/octet-stream\r\n\r\n"
                
                with open(filepath, "rb") as f:
                    body += f.read()
                
                body += b"\r\n"
                body += f"--{boundary}--\r\n".encode()
                
                def do_upload():
                    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        return resp.status == 200

                success = await asyncio.to_thread(do_upload)
                if success:
                        status_text.value = "✓ Upload Successful!"
                        status_text.color = "green"
                        # Reset UI after successful upload
                        preview_image.visible = False
                        confirm_row.visible = False
                        scan_button.visible = True
            except urllib.error.HTTPError as err:
                status_text.value = f"Server Error: {err.code}"
                status_text.color = "red"
            except Exception as ex:
                status_text.value = f"Upload Error: {str(ex)[:30]}"
                status_text.color = "red"
            await page.update_async()

        async def on_confirm(e):
            if preview_image.src:
                await upload_file(preview_image.src)

        async def on_cancel(e):
            preview_image.visible = False
            confirm_row.visible = False
            scan_button.visible = True
            status_text.value = "Waiting for request..."
            status_text.color = "blue"
            await page.update_async()

        async def on_disconnect(e):
            APP_STATE["server_url"] = ""
            APP_STATE["token"] = ""
            await show_connect_view()

        confirm_btn = ft.IconButton(
            icon="check_circle",
            icon_color="green",
            icon_size=60,
            on_click=on_confirm,
            tooltip="Send to PC"
        )
        cancel_btn = ft.IconButton(
            icon="cancel",
            icon_color="red",
            icon_size=60,
            on_click=on_cancel,
            tooltip="Retake"
        )
        confirm_row.controls = [cancel_btn, confirm_btn]

        # Polling Logic for Desktop Trigger
        async def poll_server():
            while APP_STATE["token"]:
                try:
                    url = f"{APP_STATE['server_url']}/status?token={APP_STATE['token']}"
                    def check_status():
                        with urllib.request.urlopen(url, timeout=2) as r:
                            if r.status == 200:
                                return json.loads(r.read().decode())
                        return None
                    
                    data = await asyncio.to_thread(check_status)
                    if data and data.get("scan_requested"):
                        await on_scan_click(None)
                except:
                    pass
                await asyncio.sleep(1)
        
        page.run_task(poll_server)

        page.appbar = ft.AppBar(
            title=ft.Text("Scan Document"),
            bgcolor="surfaceVariant"
        )
        
        page.add(
            scan_button,
            preview_image,
            confirm_row,
            status_text,
            ft.Button("Disconnect", on_click=on_disconnect, color="red")
        )

    # Show initial view
    await show_connect_view()


if __name__ == "__main__":
    ft.run(main)
