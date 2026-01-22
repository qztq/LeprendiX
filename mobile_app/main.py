import flet as ft
import requests
import threading
import time

# Global state to hold connection details
APP_STATE = {
    "server_url": "",
    "token": ""
}

def main(page: ft.Page):
    page.title = "LeprendiX Mobile"
    page.theme_mode = ft.ThemeMode.DARK
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    def route_change(route):
        page.views.clear()
        
        # --- VIEW 1: CONNECT ---
        if page.route == "/":
            
            ip_field = ft.TextField(label="Server IP:Port", hint_text="e.g. 192.168.1.5:5000", text_align=ft.TextAlign.CENTER)
            token_field = ft.TextField(label="Token", hint_text="Session Token", password=True, can_reveal_password=True, text_align=ft.TextAlign.CENTER)
            status_text = ft.Text("", color="red")

            def on_connect_click(e):
                if not ip_field.value or not token_field.value:
                    status_text.value = "Please enter IP and Token from Desktop"
                    page.update()
                    return
                
                status_text.value = "Connecting..."
                status_text.color = "yellow"
                page.update()
                
                # Construct URL
                base_url = f"http://{ip_field.value}"
                try:
                    # Verify connection
                    resp = requests.post(f"{base_url}/verify", json={"token": token_field.value}, timeout=3)
                    if resp.status_code == 200:
                        APP_STATE["server_url"] = base_url
                        APP_STATE["token"] = token_field.value
                        page.go("/upload")
                    else:
                        status_text.value = "Invalid Token or Server Error"
                        status_text.color = "red"
                except Exception as ex:
                    status_text.value = f"Connection Failed: {ex}"
                    status_text.color = "red"
                page.update()

            page.views.append(
                ft.View(
                    "/",
                    [
                        ft.AppBar(title=ft.Text("Connect to LeprendiX"), bgcolor=ft.colors.SURFACE_VARIANT),
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(name=ft.icons.CAST_CONNECTED, size=64),
                                ft.Text("Enter details displayed on Desktop:", size=16),
                                ip_field,
                                token_field,
                                ft.ElevatedButton("Connect", on_click=on_connect_click),
                                status_text
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=20,
                            expand=True
                        )
                    ]
                )
            )

        # --- VIEW 2: UPLOAD ---
        elif page.route == "/upload":
            
            status_text = ft.Text("Ready to scan document", size=16)
            scan_button = ft.ElevatedButton("Take Photo / Select Image", height=50)
            
            # Preview UI elements
            preview_image = ft.Image(src="", visible=False, height=400, fit=ft.ImageFit.CONTAIN)
            confirm_row = ft.Row(visible=False, alignment=ft.MainAxisAlignment.CENTER, spacing=20)
            
            def on_dialog_result(e: ft.FilePickerResultEvent):
                if e.files:
                    path = e.files[0].path
                    # Show preview instead of uploading immediately
                    preview_image.src = path
                    preview_image.visible = True
                    confirm_row.visible = True
                    scan_button.visible = False
                    status_text.value = "Review Image"
                    page.update()

            # FilePicker handles Camera/Gallery on mobile
            file_picker = ft.FilePicker(on_result=on_dialog_result)
            page.overlay.append(file_picker)
            page.update()

            def on_scan_click(e):
                file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
            
            scan_button.on_click = on_scan_click

            def upload_file(filepath):
                status_text.value = "Uploading..."
                page.update()
                
                try:
                    url = f"{APP_STATE['server_url']}/upload"
                    with open(filepath, "rb") as f:
                        files = {"image": f}
                        data = {"token": APP_STATE["token"]}
                        resp = requests.post(url, files=files, data=data, timeout=10)
                    
                    if resp.status_code == 200:
                        status_text.value = "Upload Successful! Check Desktop."
                        status_text.color = "green"
                        # Reset UI after successful upload
                        preview_image.visible = False
                        confirm_row.visible = False
                        scan_button.visible = True
                    else:
                        status_text.value = f"Server Error: {resp.text}"
                        status_text.color = "red"
                except Exception as ex:
                    status_text.value = f"Upload Error: {ex}"
                    status_text.color = "red"
                page.update()

            def on_confirm(e):
                if preview_image.src:
                    upload_file(preview_image.src)

            def on_cancel(e):
                preview_image.visible = False
                confirm_row.visible = False
                scan_button.visible = True
                status_text.value = "Cancelled."
                page.update()

            confirm_btn = ft.IconButton(icon=ft.icons.CHECK_CIRCLE, icon_color="green", icon_size=60, on_click=on_confirm, tooltip="Send to PC")
            cancel_btn = ft.IconButton(icon=ft.icons.CANCEL, icon_color="red", icon_size=60, on_click=on_cancel, tooltip="Retake")
            confirm_row.controls = [cancel_btn, confirm_btn]

            # Polling Logic for Desktop Trigger
            def poll_server():
                while True:
                    if page.route != "/upload": break
                    try:
                        url = f"{APP_STATE['server_url']}/status?token={APP_STATE['token']}"
                        r = requests.get(url, timeout=2)
                        if r.status_code == 200 and r.json().get("scan_requested"):
                            on_scan_click(None)
                    except:
                        pass
                    time.sleep(1)
            
            threading.Thread(target=poll_server, daemon=True).start()

            page.views.append(
                ft.View(
                    "/upload",
                    [
                        ft.AppBar(title=ft.Text("Scan Document"), bgcolor=ft.colors.SURFACE_VARIANT),
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(name=ft.icons.DOCUMENT_SCANNER, size=50),
                                scan_button,
                                preview_image,
                                confirm_row,
                                status_text,
                                ft.ElevatedButton("Disconnect", on_click=lambda _: page.go("/"), color="red")
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=20,
                            expand=True
                        )
                    ]
                )
            )
        
        page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go(page.route)

ft.app(target=main)
