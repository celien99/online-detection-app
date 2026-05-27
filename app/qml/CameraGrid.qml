import QtQuick
import QtQuick.Layouts

GridLayout {
    id: grid

    columns: 2
    rows: 2
    rowSpacing: 4
    columnSpacing: 4

    CameraTile {
        Layout.fillWidth: true
        Layout.fillHeight: true
        cameraId: "camera_01"
    }
    CameraTile {
        Layout.fillWidth: true
        Layout.fillHeight: true
        cameraId: "camera_02"
    }
    CameraTile {
        Layout.fillWidth: true
        Layout.fillHeight: true
        cameraId: "camera_03"
    }
    CameraTile {
        Layout.fillWidth: true
        Layout.fillHeight: true
        cameraId: "camera_04"
    }
}
