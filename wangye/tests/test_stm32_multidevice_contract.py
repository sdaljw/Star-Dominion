from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / 'Stm32Window.tsx'
COMPONENTS = Path(__file__).resolve().parents[1] / 'stm32'


def read_source():
    return SOURCE.read_text(encoding='utf-8')


def read_component(name):
    return (COMPONENTS / name).read_text(encoding='utf-8')


def test_screen_consumes_snapshots_and_has_selection_state():
    source = read_source()
    assert 'selectedDeviceId' in source
    assert 'json.devices' in source
    assert 'logsByDevice' in source
    assert 'normalizeDevice' in source
    assert 'handlePayload' in source


def test_screen_has_per_device_layers_and_targeted_command():
    source = read_source()
    assert '/send_cmd?device_id=' in source
    assert 'encodeURIComponent(selectedDeviceId)' in source
    map_surface = read_component('MapSurface.tsx')
    assert 'markerRefsRef' in map_surface
    assert 'polylineRefsRef' in map_surface
    assert 'pathsRef' in map_surface


def test_screen_removes_singleton_map_refs():
    source = read_source()
    assert 'markerRef.current' not in source
    assert 'polylineRef.current' not in source


def test_screen_has_device_list_selected_details_and_summary():
    source = read_source()
    assert 'onlineDeviceCount' in source
    assert 'sortedDevices.length' in source
    selector = read_component('DeviceSelector.tsx')
    assert '等待在线设备' in selector
    assert 'device.device_id === value' in selector
    assert 'formatDataAge' in read_component('Um980Panel.tsx')


def test_screen_keeps_legacy_gngga_compatibility():
    source = read_source()
    telemetry = read_component('telemetry.ts')
    assert 'parseGnggaMessage' in telemetry
    assert 'normalizeDevice' in source
    assert 'setDevices((current)' in source


def test_screen_keeps_age_polling_while_websocket_is_connected():
    source = read_source()
    onopen_start = source.index('ws.onopen = () => {')
    onclose_start = source.index('ws.onclose = () => {', onopen_start)
    onopen_block = source[onopen_start:onclose_start]
    assert 'clearInterval(fallbackInterval)' not in onopen_block
    assert 'fallbackInterval = setInterval(fetchFallback, 1000)' in source


def test_screen_uses_componentized_dashboard_and_shared_selection():
    source = read_source()
    for token in (
        "./stm32/MapSurface",
        "./stm32/LeftTelemetryDock",
        "./stm32/AlertStack",
        "./stm32/CommandPanel",
        "./stm32/NmeaPanel",
        "./stm32/NotificationPanel",
        "selectedDeviceId",
        "setSelectedDeviceId",
    ):
        assert token in source
    dock = read_component('LeftTelemetryDock.tsx')
    for token in ('./Um980Panel', './ImuPanel', './DisplacementPanel'):
        assert token in dock
    assert './DeviceSelector' in read_component('Um980Panel.tsx')
    for name in ('Um980Panel.tsx', 'ImuPanel.tsx', 'DisplacementPanel.tsx', 'CommandPanel.tsx', 'NmeaPanel.tsx'):
        component = read_component(name)
        assert 'selectedDeviceId' in component
        assert 'onSelectDevice' in component


def test_um980_contract_has_seven_fields_without_quality_q():
    um980 = read_component('Um980Panel.tsx')
    for token in ("经度", "纬度", "海拔", "定位状态", "卫星数", "温度", "湿度"):
        assert token in um980
    assert "质量 q" not in um980


def test_nmea_logs_use_stored_timestamps_not_render_time():
    source = read_source()
    nmea = read_component('NmeaPanel.tsx')
    assert "interface LogEntry" in read_component('types.ts')
    assert "timestamp" in nmea
    assert "server_timestamp" in source
    assert "new Date().toLocaleTimeString" not in source
    assert "new Date().toLocaleTimeString" not in nmea


def test_page_has_map_surface_and_alert_stack():
    source = read_source()
    assert "MapSurface" in source
    assert "AlertStack" in source
    assert "质量 q" not in source
