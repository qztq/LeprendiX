import flet as ft
import requests

# Global state to hold connection details
APP_STATE = {
    "server_url": "",
    "token": ""
}

def main(page: ft.Page):
    page.title = "LeprendiX Scanner"
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
            
            def on_dialog_result(e: ft.FilePickerResultEvent):
                if e.files:
                    path = e.files[0].path
                    upload_file(path)

            # FilePicker handles Camera/Gallery on mobile
            file_picker = ft.FilePicker(on_result=on_dialog_result)
            page.overlay.append(file_picker)
            page.update()

            def on_scan_click(e):
                file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)

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
                    else:
                        status_text.value = f"Server Error: {resp.text}"
                        status_text.color = "red"
                except Exception as ex:
                    status_text.value = f"Upload Error: {ex}"
                    status_text.color = "red"
                page.update()

            page.views.append(
                ft.View(
                    "/upload",
                    [
                        ft.AppBar(title=ft.Text("Scan Document"), bgcolor=ft.colors.SURFACE_VARIANT),
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(name=ft.icons.DOCUMENT_SCANNER, size=100),
                                ft.ElevatedButton("Take Photo / Select Image", on_click=on_scan_click, height=50),
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
