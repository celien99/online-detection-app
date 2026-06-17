import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import "components"
import styles

Rectangle {
    id: modelDeployScreen
    color: Theme.bgPrimary

    property var viewModel: null
    property var seatModelOptions: viewModel ? viewModel.seatModelOptions : []
    property var cameraOptions: viewModel ? viewModel.cameraOptions : []
    property var importCameraOptions: cameraOptions.length > 1 ? cameraOptions.slice(1) : []
    property var modelTypeOptions: [
        { id: "", label: qsTr("全部类型") },
        { id: "patchcore", label: "patchcore" },
        { id: "filter_classifier", label: "filter_classifier" },
        { id: "rules", label: "rules" }
    ]
    property var importTypeOptions: [
        { id: "patchcore", label: "patchcore" },
        { id: "filter_classifier", label: "filter_classifier" },
        { id: "rules", label: "rules" }
    ]

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
        ignoreUnknownSignals: true
        function onToast(message, level) { toast.show(message, level); }
    }

    Component.onCompleted: {
        if (modelDeployScreen.viewModel) {
            modelDeployScreen.viewModel.checkPlatformHealth();
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLG
        spacing: Theme.spacingMD

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD

            Text {
                text: qsTr("模型部署")
                color: Theme.textPrimary
                font.pixelSize: Theme.fontSizeLG
                font.bold: true
            }

            Text {
                text: modelDeployScreen.viewModel
                      ? qsTr("当前型号: ") + (modelDeployScreen.viewModel.selectedSeatModelId || qsTr("未选择"))
                      : qsTr("当前型号: 未选择")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeSM
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            ActionButton {
                buttonText: qsTr("校验激活版本")
                bgColor: Theme.bgTertiary
                textColor: Theme.textPrimary
                implicitHeight: 36
                Layout.preferredWidth: 128
                onClicked: {
                    if (modelDeployScreen.viewModel) {
                        modelDeployScreen.viewModel.verifyActiveVersions();
                    }
                }
            }

            ActionButton {
                buttonText: qsTr("手动导入")
                bgColor: Theme.accent
                implicitHeight: 36
                Layout.preferredWidth: 104
                enabled: modelDeployScreen.importCameraOptions.length > 0
                onClicked: importDialog.open()
            }

            ActionButton {
                buttonText: qsTr("平台同步")
                bgColor: Theme.accentGreen
                textColor: "#000000"
                implicitHeight: 36
                Layout.preferredWidth: 104
                onClicked: {
                    if (modelDeployScreen.viewModel) {
                        modelDeployScreen.viewModel.syncFromPlatform();
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD

            ComboBox {
                id: seatModelCombo
                Layout.preferredWidth: 240
                Layout.preferredHeight: 38
                model: modelDeployScreen.seatModelOptions
                textRole: "label"
                valueRole: "id"
                onActivated: {
                    if (modelDeployScreen.viewModel) {
                        modelDeployScreen.viewModel.setSeatModel(currentValue || "");
                    }
                }
            }

            ComboBox {
                id: cameraFilter
                Layout.preferredWidth: 180
                Layout.preferredHeight: 38
                model: modelDeployScreen.cameraOptions
                textRole: "label"
                valueRole: "id"
                onActivated: {
                    if (modelDeployScreen.viewModel) {
                        modelDeployScreen.viewModel.setFilterCamera(currentValue || "");
                    }
                }
            }

            ComboBox {
                id: typeFilter
                Layout.preferredWidth: 180
                Layout.preferredHeight: 38
                model: modelDeployScreen.modelTypeOptions
                textRole: "label"
                valueRole: "id"
                onActivated: {
                    if (modelDeployScreen.viewModel) {
                        modelDeployScreen.viewModel.setFilterType(currentValue || "");
                    }
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: runtimeBadgeText.implicitWidth + 28
                Layout.preferredHeight: 32
                radius: Theme.radiusSM
                color: runtimeStatusColor(modelDeployScreen.viewModel ? modelDeployScreen.viewModel.runtimeStatus : "", true)
                border {
                    width: 1
                    color: runtimeStatusColor(modelDeployScreen.viewModel ? modelDeployScreen.viewModel.runtimeStatus : "", false)
                }
                Text {
                    id: runtimeBadgeText
                    anchors.centerIn: parent
                    text: modelDeployScreen.viewModel
                          ? qsTr("运行时 ") + modelDeployScreen.viewModel.runtimeStatus
                          : qsTr("运行时 未知")
                    color: runtimeStatusColor(modelDeployScreen.viewModel ? modelDeployScreen.viewModel.runtimeStatus : "", false)
                    font.pixelSize: Theme.fontSizeXS
                    font.bold: true
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.spacingMD

            Repeater {
                model: [
                    { label: qsTr("离线平台"), valueKey: "syncStatus", color: Theme.accentGreen },
                    { label: qsTr("历史版本"), valueKey: "modelCount", color: Theme.accent },
                    { label: qsTr("激活版本"), valueKey: "runtimeCount", color: Theme.statusOK },
                    { label: qsTr("最近同步"), valueKey: "lastSyncTime", color: Theme.statusWarning }
                ]
                delegate: Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 66
                    color: Theme.cardGlass
                    radius: Theme.radiusSM
                    border { width: 1; color: Theme.cardGlassBorder }

                    ColumnLayout {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: Theme.spacingMD
                        anchors.rightMargin: Theme.spacingMD
                        spacing: 4
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.fillWidth: true
                            text: modelData.label
                            color: Theme.textSecondary
                            font.pixelSize: Theme.fontSizeXS
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignHCenter
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: summaryValue(modelData.valueKey)
                            color: modelData.color
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacingMD

            Rectangle {
                Layout.preferredWidth: Math.max(360, modelDeployScreen.width * 0.38)
                Layout.fillHeight: true
                color: Theme.bgSecondary
                radius: Theme.radiusSM
                border { width: 1; color: Theme.borderDefault }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMD
                    spacing: Theme.spacingSM

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: qsTr("运行时已应用版本")
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeMD
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: modelDeployScreen.viewModel
                                  ? String(modelDeployScreen.viewModel.activeRuntimeVersions.length)
                                  : "0"
                            color: Theme.accent
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                        }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.borderDefault }

                    ListView {
                        id: runtimeList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: modelDeployScreen.viewModel ? modelDeployScreen.viewModel.activeRuntimeVersions : []
                        spacing: Theme.spacingSM
                        clip: true

                        delegate: Rectangle {
                            width: ListView.view.width
                            height: Math.max(82, runtimeInfo.implicitHeight + Theme.spacingMD * 2)
                            color: modelData.exists ? Theme.cardGlass : Theme.statusNGDim
                            radius: Theme.radiusSM
                            border {
                                width: 1
                                color: modelData.exists ? Theme.cardGlassBorder : Theme.statusNG
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacingMD
                                spacing: Theme.spacingSM

                                Rectangle {
                                    Layout.preferredWidth: 68
                                    Layout.preferredHeight: 28
                                    radius: Theme.radiusSM
                                    color: modelData.exists ? Theme.statusOKDim : Theme.statusNGDim
                                    border {
                                        width: 1
                                        color: modelData.exists ? Theme.statusOK : Theme.statusNG
                                    }
                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.exists ? qsTr("READY") : qsTr("MISSING")
                                        color: modelData.exists ? Theme.statusOK : Theme.statusNG
                                        font.pixelSize: Theme.fontSizeXS
                                        font.bold: true
                                    }
                                }

                                ColumnLayout {
                                    id: runtimeInfo
                                    Layout.fillWidth: true
                                    spacing: 3

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.camera_id + " / " + modelData.model_type
                                        color: Theme.textPrimary
                                        font.pixelSize: Theme.fontSizeSM
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.file_name || modelData.file_id
                                        color: Theme.textSecondary
                                        font.pixelSize: Theme.fontSizeXS
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.sha256 ? modelData.sha256.substring(0, 12) : ""
                                        visible: text !== ""
                                        color: Theme.textMuted
                                        font.pixelSize: Theme.fontSizeXS
                                        elide: Text.ElideRight
                                    }
                                }

                                ActionButton {
                                    buttonText: qsTr("回滚")
                                    bgColor: Theme.bgTertiary
                                    textColor: Theme.textPrimary
                                    implicitHeight: 30
                                    Layout.preferredWidth: 64
                                    onClicked: {
                                        if (modelDeployScreen.viewModel) {
                                            modelDeployScreen.viewModel.rollback(modelData.camera_id, modelData.model_type);
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: runtimeList.count === 0
                            text: qsTr("当前型号还没有激活到运行时的模型")
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSizeSM
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.bgSecondary
                radius: Theme.radiusSM
                border { width: 1; color: Theme.borderDefault }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spacingMD
                    spacing: Theme.spacingSM

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: qsTr("版本历史")
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeMD
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: modelDeployScreen.viewModel
                                  ? String(modelDeployScreen.viewModel.modelFiles.length)
                                  : "0"
                            color: Theme.accent
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: true
                        }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.borderDefault }

                    ListView {
                        id: fileList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: modelDeployScreen.viewModel ? modelDeployScreen.viewModel.modelFiles : []
                        spacing: Theme.spacingSM
                        clip: true

                        delegate: Rectangle {
                            width: ListView.view.width
                            height: Math.max(76, fileInfo.implicitHeight + Theme.spacingMD * 2)
                            color: modelData.is_active ? Theme.accentGreenDim : Theme.cardGlass
                            radius: Theme.radiusSM
                            border {
                                width: 1
                                color: modelData.is_active ? Theme.accentGreen : Theme.cardGlassBorder
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: Theme.spacingMD
                                spacing: Theme.spacingMD

                                ColumnLayout {
                                    id: fileInfo
                                    Layout.fillWidth: true
                                    spacing: 3

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.file_name || modelData.id
                                        color: Theme.textPrimary
                                        font.pixelSize: Theme.fontSizeSM
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: Theme.spacingSM
                                        Text {
                                            text: modelData.camera_id || ""
                                            color: Theme.textSecondary
                                            font.pixelSize: Theme.fontSizeXS
                                            elide: Text.ElideRight
                                            Layout.maximumWidth: 120
                                        }
                                        Text {
                                            text: modelData.model_type || ""
                                            color: Theme.textMuted
                                            font.pixelSize: Theme.fontSizeXS
                                        }
                                        Text {
                                            text: modelData.platform_version ? ("v" + modelData.platform_version) : ""
                                            color: Theme.accent
                                            font.pixelSize: Theme.fontSizeXS
                                            visible: text !== ""
                                        }
                                        Text {
                                            text: modelData.sha256 ? modelData.sha256.substring(0, 8) : ""
                                            color: Theme.textMuted
                                            font.pixelSize: Theme.fontSizeXS
                                            visible: text !== ""
                                        }
                                    }
                                }

                                ActionButton {
                                    buttonText: modelData.is_active ? qsTr("已激活") : qsTr("激活")
                                    bgColor: modelData.is_active ? Theme.bgTertiary : Theme.statusOK
                                    textColor: modelData.is_active ? Theme.textMuted : "#000000"
                                    enabled: !modelData.is_active
                                    implicitHeight: 30
                                    Layout.preferredWidth: 72
                                    onClicked: {
                                        if (modelDeployScreen.viewModel) {
                                            modelDeployScreen.viewModel.activateVersion(modelData.id);
                                        }
                                    }
                                }

                                ActionButton {
                                    buttonText: qsTr("删除")
                                    bgColor: Theme.statusNGDim
                                    textColor: Theme.statusNG
                                    visible: !modelData.is_active
                                    implicitHeight: 30
                                    Layout.preferredWidth: 60
                                    onClicked: {
                                        if (modelDeployScreen.viewModel) {
                                            modelDeployScreen.viewModel.deleteModelFile(modelData.id);
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: fileList.count === 0
                            text: qsTr("没有匹配的模型历史")
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontSizeSM
                        }
                    }
                }
            }

            EmptyState {
                anchors.fill: parent
                visible: fileList.count === 0
                title: qsTr("暂无模型文件")
                message: qsTr("可手动导入模型文件，或从离线平台同步可用版本。")
                badgeText: qsTr("MODEL")
                accentColor: Theme.accent
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
                text: qsTr("目标相机")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
                font.weight: Font.Medium
            }
            ComboBox {
                id: importCameraCombo
                Layout.fillWidth: true
                Layout.preferredHeight: 38
                model: modelDeployScreen.importCameraOptions
                textRole: "label"
                valueRole: "id"
            }

            Text {
                Layout.fillWidth: true
                text: qsTr("模型类型")
                color: Theme.textSecondary
                font.pixelSize: Theme.fontSizeXS
                font.weight: Font.Medium
            }
            ComboBox {
                id: importTypeCombo
                Layout.fillWidth: true
                Layout.preferredHeight: 38
                model: modelDeployScreen.importTypeOptions
                textRole: "label"
                valueRole: "id"
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: qsTr("选择模型文件")
        nameFilters: [qsTr("Model files (*.pt *.pth *.onnx *.json)"), qsTr("All files (*)")]
        onAccepted: {
            if (modelDeployScreen.viewModel && selectedFile && importCameraCombo.currentValue) {
                modelDeployScreen.viewModel.importModelFile(
                    importCameraCombo.currentValue,
                    importTypeCombo.currentValue || "patchcore",
                    String(selectedFile)
                );
            }
        }
    }

    function summaryValue(key) {
        if (!modelDeployScreen.viewModel) return "";
        if (key === "syncStatus") return modelDeployScreen.viewModel.syncStatus;
        if (key === "modelCount") return String(modelDeployScreen.viewModel.modelFiles.length);
        if (key === "runtimeCount") return String(modelDeployScreen.viewModel.activeRuntimeVersions.length);
        if (key === "lastSyncTime") return modelDeployScreen.viewModel.lastSyncTime || qsTr("从未");
        return "";
    }

    function runtimeStatusColor(status, dim) {
        if (status === "已应用") return dim ? Theme.statusOKDim : Theme.statusOK;
        if (status === "文件缺失") return dim ? Theme.statusNGDim : Theme.statusNG;
        return dim ? Theme.statusWarningDim : Theme.statusWarning;
    }
}
