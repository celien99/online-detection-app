import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"
import styles

Rectangle {
    id: modelDeployScreen
    color: Theme.bgPrimary

    property var viewModel: null

    ToastNotification {
        id: toast
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.spacingMD
        anchors.rightMargin: Theme.spacingMD
        z: 100
    }

    Connections {
        target: modelDeployScreen.viewModel
        function onToast(message, level) { toast.show(message, level); }
    }

    Component.onCompleted: {
        if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.checkPlatformHealth();
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: qsTr("模型部署")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                radius: Theme.radiusSM
                color: Theme.accentDim
                implicitWidth: 130; implicitHeight: 36
                Text {
                    anchors.centerIn: parent
                    text: qsTr("📂 手动导入")
                    color: Theme.accent
                    font.pixelSize: Theme.fontSizeSM
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: importDialog.open()
                }
            }
            Rectangle {
                radius: Theme.radiusSM
                color: Theme.accentGreenDim
                implicitWidth: 150; implicitHeight: 36
                Text {
                    anchors.centerIn: parent
                    text: qsTr("🔄 从离线平台同步")
                    color: Theme.accentGreen
                    font.pixelSize: Theme.fontSizeSM
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.syncFromPlatform();
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD
            Repeater {
                model: [
                    { label: qsTr("离线平台"), valueKey: "syncStatus", color: Theme.accentGreen },
                    { label: qsTr("本地模型"), valueKey: "modelCount", color: Theme.accent },
                    { label: qsTr("最近同步"), valueKey: "lastSyncTime", color: Theme.statusWarning }
                ]
                delegate: Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 70
                    color: Theme.cardGlass
                    radius: Theme.radiusMD
                    border { width: 1; color: Theme.cardGlassBorder }
                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 4
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: modelData.label
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: {
                                if (modelData.valueKey === "syncStatus") return modelDeployScreen.viewModel ? modelDeployScreen.viewModel.syncStatus : "offline";
                                if (modelData.valueKey === "modelCount") return modelDeployScreen.viewModel ? String(modelDeployScreen.viewModel.modelFiles.length) : "0";
                                if (modelData.valueKey === "lastSyncTime") return modelDeployScreen.viewModel ? (modelDeployScreen.viewModel.lastSyncTime || qsTr("从未")) : qsTr("从未");
                                return "";
                            }
                            color: modelData.color
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingSM
            Text { text: qsTr("筛选:"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
            ComboBox {
                id: cameraFilter
                model: [qsTr("全部相机")]
                onCurrentTextChanged: {
                    if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.setFilterCamera(
                        currentIndex === 0 ? "" : currentText
                    );
                }
            }
            ComboBox {
                id: typeFilter
                model: [qsTr("全部类型"), "efficientad", "filter_classifier", "calibration_normalizer", "calibration_projector"]
                onCurrentTextChanged: {
                    if (modelDeployScreen.viewModel) modelDeployScreen.viewModel.setFilterType(
                        currentIndex === 0 ? "" : currentText
                    );
                }
            }
        }

        ListView {
            id: fileList
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: modelDeployScreen.viewModel ? modelDeployScreen.viewModel.modelFiles : []
            spacing: Theme.spacingSM

            delegate: Rectangle {
                width: ListView.view.width
                implicitHeight: 72
                color: modelData.is_active ? Theme.accentGreenDim : Theme.cardGlass
                radius: Theme.radiusMD
                border { width: 1; color: modelData.is_active ? Theme.accentGreen : Theme.cardGlassBorder }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMD
                    spacing: Theme.spacingMD

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: modelData.file_name || modelData.id
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                        }
                        RowLayout {
                            spacing: Theme.spacingSM
                            Text { text: modelData.camera_id || ""; color: Theme.textSecondary; font.pixelSize: Theme.fontSizeXS }
                            Text { text: modelData.model_type || ""; color: Theme.textMuted; font.pixelSize: Theme.fontSizeXS }
                            Text {
                                text: modelData.platform_version ? ("v" + modelData.platform_version) : ""
                                color: Theme.accent
                                font.pixelSize: Theme.fontSizeXS
                                visible: text !== ""
                            }
                            Text {
                                text: modelData.sha256 ? modelData.sha256.substring(0, 8) + "..." : ""
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSizeXS
                                visible: text !== ""
                            }
                        }
                    }

                    RowLayout {
                        spacing: Theme.spacingXS
                        Rectangle {
                            radius: Theme.radiusSM
                            color: modelData.is_active ? Theme.bgTertiary : Theme.accentGreenDim
                            implicitWidth: modelData.is_active ? 56 : 48
                            implicitHeight: 28
                            Text {
                                anchors.centerIn: parent
                                text: modelData.is_active ? qsTr("已激活") : qsTr("激活")
                                color: modelData.is_active ? Theme.textMuted : Theme.accentGreen
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: !modelData.is_active
                                onClicked: modelDeployScreen.viewModel.activateVersion(modelData.id)
                            }
                        }
                        Rectangle {
                            radius: Theme.radiusSM
                            color: Qt.rgba(0.973, 0.318, 0.286, 0.1)
                            implicitWidth: 40; implicitHeight: 28
                            visible: !modelData.is_active
                            Text {
                                anchors.centerIn: parent
                                text: qsTr("删除")
                                color: Theme.statusNG
                                font.pixelSize: Theme.fontSizeXS
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: modelDeployScreen.viewModel.deleteModelFile(modelData.id)
                            }
                        }
                    }
                }
            }
        }
    }

    IndustrialDialog {
        id: importDialog
        title: qsTr("导入模型文件")
        acceptText: qsTr("选择文件")
        showCancel: true
        onAccepted: fileDialog.open()

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                Layout.fillWidth: true
                text: qsTr("相机 ID")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
                font.weight: Font.Medium
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: importCamInput.activeFocus ? Qt.rgba(1, 1, 1, 0.06) : Theme.cardGlass
                radius: Theme.radiusSM
                border { width: 1; color: importCamInput.activeFocus ? Theme.accent : Theme.cardGlassBorder }
                Behavior on border.color { ColorAnimation { duration: Theme.animFast } }
                TextInput {
                    id: importCamInput
                    anchors.fill: parent
                    anchors.leftMargin: 12; anchors.rightMargin: 12
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                    activeFocusOnPress: true
                    selectByMouse: true
                    text: "cam_front"
                }
            }

            Text {
                Layout.fillWidth: true
                text: qsTr("模型类型")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
                font.weight: Font.Medium
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 38
                color: Theme.cardGlass
                radius: Theme.radiusSM
                border { width: 1; color: Theme.cardGlassBorder }

                Text {
                    id: importTypeLabel
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    text: importTypeCombo.currentText
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeSM
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: "▼"
                    color: Theme.textSecondary
                    font.pixelSize: 9
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: importTypePopup.open()
                }
                Popup {
                    id: importTypePopup
                    y: parent.height + 4
                    x: 0
                    width: parent.width
                    padding: 4
                    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                    background: Rectangle {
                        color: Theme.bgSecondary
                        radius: Theme.radiusMD
                        border { width: 1; color: Theme.accent }
                    }
                    contentItem: ColumnLayout {
                        spacing: 2
                        Repeater {
                            model: ["efficientad", "filter_classifier", "calibration_normalizer", "calibration_projector"]
                            delegate: Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 34
                                radius: Theme.radiusSM
                                color: importTypeCombo.currentIndex === index ? Theme.accentDim
                                       : (hoverHandler.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent")
                                Behavior on color { ColorAnimation { duration: Theme.animFast } }
                                Text {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData
                                    color: importTypeCombo.currentIndex === index ? Theme.accent : Theme.textPrimary
                                    font.pixelSize: Theme.fontSizeSM
                                    font.bold: importTypeCombo.currentIndex === index
                                }
                                MouseArea {
                                    id: hoverHandler
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        importTypeCombo.currentIndex = index;
                                        importTypePopup.close();
                                    }
                                }
                            }
                        }
                    }
                }
                ComboBox {
                    id: importTypeCombo
                    visible: false
                    model: ["efficientad", "filter_classifier", "calibration_normalizer", "calibration_projector"]
                    currentIndex: 0
                }
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: qsTr("选择模型文件")
        nameFilters: [qsTr("Model files (*.pt *.pth *.onnx)"), qsTr("All files (*)")]
        onAccepted: {
            if (modelDeployScreen.viewModel && selectedFile) {
                modelDeployScreen.viewModel.importModelFile(
                    importCamInput.text || "cam_front",
                    importTypeCombo.currentText,
                    String(selectedFile)
                );
            }
        }
    }
}
