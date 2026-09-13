import reflex as rx

config = rx.Config(
    app_name="refit",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                appearance="inherit",
                accent_color="grass",
                gray_color="sand",
                radius="large",
            )
        ),
    ]
)