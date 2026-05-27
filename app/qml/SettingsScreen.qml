import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "components"
import styles

Rectangle {
    id: settingsScreen
    color: Theme.bgPrimary

    property int selectedIndex: 0
    property var viewModel: null

    // ── Helper: read a parsed value from the ViewModel ──
    function readValue(path, fallback) {
        if (!settingsScreen.viewModel) return fallback;
        var raw = settingsScreen.viewModel.getValue(path);
        if (raw === "") return fallback;
        try { return JSON.parse(raw); } catch (e) { return raw; }
    }

    // ── File dialogs ──
    FileDialog {
        id: importDialog
        title: qsTr("导入配置文件")
        nameFilters: [qsTr("JSON 文件 (*.json)"), qsTr("所有文件 (*)")]
        fileMode: FileDialog.OpenFile
        onAccepted: {
            var path = decodeURIComponent(String(importDialog.selectedFile).replace(/^file:\/\//, ""));
            if (settingsScreen.viewModel) {
                settingsScreen.viewModel.importConfig(path);
            }
        }
    }

    FileDialog {
        id: exportDialog
        title: qsTr("导出配置文件")
        nameFilters: [qsTr("JSON 文件 (*.json)"), qsTr("所有文件 (*)")]
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        onAccepted: {
            var path = decodeURIComponent(String(exportDialog.selectedFile).replace(/^file:\/\//, ""));
            if (settingsScreen.viewModel) {
                settingsScreen.viewModel.exportConfig(path);
            }
        }
    }

    // ── ViewModel signal connections ──
    Connections {
        target: settingsScreen.viewModel
        function onSaved() {
            toastNotification.show(qsTr("配置保存成功"), "success");
        }
        function onSaveFailed(error) {
            toastNotification.show(qsTr("保存失败: ") + error, "error");
        }
        function onImportSucceeded() {
            toastNotification.show(qsTr("配置导入成功"), "success");
        }
        function onImportFailed(error) {
            toastNotification.show(qsTr("导入失败: ") + error, "error");
        }
        function onReloaded() {
            toastNotification.show(qsTr("配置已重新加载"), "success");
        }
    }

    // ── Inline components ─────────────────────────────────

    // Toggle switch for boolean config values
    component ToggleSwitch: Rectangle {
        id: toggleRoot
        property string configPath: ""
        property bool checked: false

        implicitWidth: 120
        implicitHeight: 28
        radius: height / 2
        color: toggleRoot.checked ? Theme.statusOKDim : Theme.bgTertiary
        border {
            width: 1
            color: toggleRoot.checked ? Theme.statusOK : Theme.borderDefault
        }

        Behavior on color { ColorAnimation { duration: Theme.animFast } }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            text: toggleRoot.checked ? qsTr("已启用") : qsTr("已禁用")
            color: toggleRoot.checked ? Theme.statusOK : Theme.textSecondary
            font.pixelSize: Theme.fontSizeXS
            font.bold: true
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                var newVal = !toggleRoot.checked;
                toggleRoot.checked = newVal;
                if (toggleRoot.configPath && settingsScreen.viewModel) {
                    settingsScreen.viewModel.setValue(toggleRoot.configPath, JSON.stringify(newVal));
                }
            }
        }
    }

    // Text input field for string/numeric config values
    component SettingsField: Rectangle {
        id: fieldRoot
        property string configPath: ""
        property string displayValue: ""
        property bool isNumeric: false

        implicitHeight: 36
        implicitWidth: 280
        color: Theme.cardGlass
        radius: Theme.radiusSM
        border { width: 1; color: Theme.cardGlassBorder }

        TextInput {
            id: fieldInput
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            verticalAlignment: TextInput.AlignVCenter
            text: fieldRoot.displayValue
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeSM
            selectByMouse: true

            onEditingFinished: {
                if (!settingsScreen.viewModel || !fieldRoot.configPath) return;
                var rawText = fieldInput.text;
                var val;
                if (fieldRoot.isNumeric) {
                    var num = parseFloat(rawText);
                    val = isNaN(num) ? JSON.stringify(rawText) : JSON.stringify(num);
                } else {
                    val = JSON.stringify(rawText);
                }
                settingsScreen.viewModel.setValue(fieldRoot.configPath, val);
            }
        }
    }

    // Combo box / dropdown for enum config values
    component SettingsCombo: Rectangle {
        id: comboRoot
        property string configPath: ""
        property var items: []          // display texts
        property var values: []         // actual values (parallel to items; if empty, items ARE the values)
        property string currentValue: ""

        implicitHeight: 36
        implicitWidth: 280
        color: comboMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : Theme.cardGlass
        radius: Theme.radiusSM
        border { width: 1; color: comboPopup.visible ? Theme.accent : Theme.cardGlassBorder }

        Behavior on border.color { ColorAnimation { duration: Theme.animFast } }

        function displayTextFor(val) {
            if (comboRoot.values.length > 0) {
                for (var i = 0; i < comboRoot.values.length; i++) {
                    if (comboRoot.values[i] === val && i < comboRoot.items.length)
                        return comboRoot.items[i];
                }
            }
            return val;
        }

        function actualFor(display) {
            if (comboRoot.values.length > 0) {
                for (var i = 0; i < comboRoot.items.length; i++) {
                    if (comboRoot.items[i] === display && i < comboRoot.values.length)
                        return comboRoot.values[i];
                }
            }
            return display;
        }

        Text {
            id: comboDisplayText
            anchors.left: parent.left
            anchors.leftMargin: 10
            anchors.right: comboArrow.left
            anchors.rightMargin: 4
            anchors.verticalCenter: parent.verticalCenter
            text: comboRoot.displayTextFor(comboRoot.currentValue)
            color: Theme.textPrimary
            font.pixelSize: Theme.fontSizeSM
            elide: Text.ElideRight
        }

        Text {
            id: comboArrow
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: comboPopup.visible ? "▲" : "▼"
            color: comboPopup.visible ? Theme.accent : Theme.textSecondary
            font.pixelSize: 9
        }

        MouseArea {
            id: comboMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (comboPopup.visible) {
                    comboPopup.close();
                } else {
                    comboPopup.open();
                }
            }
        }

        Popup {
            id: comboPopup
            y: parent.height + 4
            x: 0
            width: Math.max(parent.width, 200)
            padding: 4
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: Theme.bgSecondary
                radius: Theme.radiusMD
                border { width: 1; color: Theme.accent }

                layer.enabled: true
                layer.effect: null
            }

            contentItem: ColumnLayout {
                spacing: 2
                Repeater {
                    model: comboRoot.items
                    delegate: Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 34
                        radius: Theme.radiusSM
                        color: {
                            if (comboRoot.actualFor(modelData) === comboRoot.currentValue)
                                return Theme.accentDim;
                            if (hoverHandler.containsMouse)
                                return Qt.rgba(1, 1, 1, 0.06);
                            return "transparent";
                        }

                        Behavior on color { ColorAnimation { duration: Theme.animFast } }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData
                            color: comboRoot.actualFor(modelData) === comboRoot.currentValue ? Theme.accent : Theme.textPrimary
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: comboRoot.actualFor(modelData) === comboRoot.currentValue
                        }

                        MouseArea {
                            id: hoverHandler
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var actual = comboRoot.actualFor(modelData);
                                comboRoot.currentValue = actual;
                                if (settingsScreen.viewModel && comboRoot.configPath) {
                                    settingsScreen.viewModel.setValue(comboRoot.configPath, JSON.stringify(actual));
                                }
                                comboPopup.close();
                            }
                        }
                    }
                }
            }
        }
    }

    // ── Main layout ──
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── Sidebar ──
        Rectangle {
            Layout.preferredWidth: 200
            Layout.fillHeight: true
            color: Theme.bgSecondary

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.spacingSM
                anchors.rightMargin: Theme.spacingSM
                anchors.topMargin: Theme.spacingSM
                anchors.bottomMargin: Theme.spacingSM
                spacing: 0

                Text {
                    text: qsTr("设置")
                    color: Theme.textPrimary
                    font.pixelSize: Theme.fontSizeMD
                    font.bold: true
                    Layout.leftMargin: Theme.spacingSM
                    Layout.topMargin: Theme.spacingSM
                    Layout.bottomMargin: Theme.spacingSM
                }

                ListView {
                    id: navList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: [
                        qsTr("相机配置"),
                        qsTr("检测模型"),
                        qsTr("PLC 通信"),
                        qsTr("离线平台"),
                        qsTr("告警设置"),
                        qsTr("存储管理"),
                        qsTr("关于系统")
                    ]
                    currentIndex: settingsScreen.selectedIndex

                    delegate: Rectangle {
                        width: navList.width - 8
                        height: 44
                        color: index === navList.currentIndex ? Theme.bgTertiary : "transparent"
                        radius: Theme.radiusSM

                        Rectangle {
                            visible: index === navList.currentIndex
                            width: 3; height: 22
                            anchors.verticalCenter: parent.verticalCenter
                            color: Theme.accent
                            radius: 1.5
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: Theme.spacingMD + Theme.spacingXS
                            text: modelData
                            color: index === navList.currentIndex ? Theme.textPrimary : Theme.textSecondary
                            font.pixelSize: Theme.fontSizeSM
                            font.bold: index === navList.currentIndex
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: settingsScreen.selectedIndex = index
                        }
                    }
                }
            }
        }

        // ── Content area ──
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bgPrimary

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Scrollable settings content
                Flickable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.leftMargin: Theme.spacingLG
                    Layout.rightMargin: Theme.spacingLG
                    Layout.topMargin: Theme.spacingLG
                    Layout.bottomMargin: 0
                    contentHeight: contentColumn.implicitHeight + Theme.spacingLG
                    clip: true
                    ScrollBar.vertical: ScrollBar {}

                    ColumnLayout {
                        id: contentColumn
                        width: parent.width
                        spacing: Theme.spacingMD

                        // ── Section header ──
                        Text {
                            text: {
                                var items = [
                                    qsTr("相机配置"),
                                    qsTr("检测模型"),
                                    qsTr("PLC 通信设置"),
                                    qsTr("离线平台设置"),
                                    qsTr("告警设置"),
                                    qsTr("存储管理"),
                                    qsTr("关于系统")
                                ];
                                return items[settingsScreen.selectedIndex] || "";
                            }
                            color: Theme.textPrimary
                            font.pixelSize: Theme.fontSizeLG
                            font.bold: true
                        }

                        // ── Section 0: Camera Config ──
                        ColumnLayout {
                            visible: settingsScreen.selectedIndex === 0
                            Layout.fillWidth: true
                            spacing: Theme.spacingSM

                            Text {
                                text: qsTr("已启用的相机列表")
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeSM
                            }

                            Repeater {
                                model: settingsScreen.readValue("cameras", [])

                                delegate: Rectangle {
                                    id: camCard
                                    Layout.fillWidth: true
                                    height: camCard.camExpanded ? camExpandedH : camCollapsedH
                                    Behavior on height { NumberAnimation { duration: Theme.animNormal; easing.type: Easing.OutCubic } }
                                    clip: true
                                    color: Theme.cardGlass
                                    radius: Theme.radiusMD
                                    border { width: 1; color: Theme.cardGlassBorder }

                                    readonly property int camCollapsedH: 56
                                    readonly property int camExpandedH: 300
                                    property bool camExpanded: false

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacingMD
                                        spacing: Theme.spacingSM

                                        // Header row (always visible, clickable)
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Theme.spacingMD
                                            Layout.minimumHeight: 32

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 2
                                                Text {
                                                    text: modelData.camera_id || ""
                                                    color: Theme.textPrimary
                                                    font.pixelSize: Theme.fontSizeSM
                                                    font.bold: true
                                                }
                                                Text {
                                                    text: qsTr("类型: ") + (modelData.type || "") + qsTr("  来源: ") + (modelData.source || "")
                                                    color: Theme.textSecondary
                                                    font.pixelSize: Theme.fontSizeXS
                                                }
                                            }

                                            StatusBadge {
                                                badgeText: modelData.enabled !== false ? qsTr("启用") : qsTr("禁用")
                                                badgeStatus: modelData.enabled !== false ? "ok" : "warning"
                                            }

                                            Text {
                                                text: camCard.camExpanded ? "▲" : "▼"
                                                color: Theme.textSecondary
                                                font.pixelSize: Theme.fontSizeXS
                                            }

                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: camCard.camExpanded = !camCard.camExpanded
                                            }
                                        }

                                        // Expanded editable fields
                                        ColumnLayout {
                                            visible: camCard.camExpanded
                                            Layout.fillWidth: true
                                            spacing: Theme.spacingSM

                                            // EfficientAD model path
                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: Theme.spacingSM
                                                Text {
                                                    text: qsTr("EfficientAD 模型:")
                                                    color: Theme.textSecondary
                                                    font.pixelSize: Theme.fontSizeXS
                                                    Layout.preferredWidth: 120
                                                }
                                                SettingsField {
                                                    Layout.fillWidth: true
                                                    configPath: "cameras." + index + ".efficientad_model_path"
                                                    displayValue: modelData.efficientad_model_path || ""
                                                }
                                            }

                                            // Filter classifier toggle
                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: Theme.spacingSM
                                                Text {
                                                    text: qsTr("Filter 分类器:")
                                                    color: Theme.textSecondary
                                                    font.pixelSize: Theme.fontSizeXS
                                                    Layout.preferredWidth: 120
                                                }
                                                ToggleSwitch {
                                                    configPath: "cameras." + index + ".filter_classifier.enabled"
                                                    checked: modelData.filter_classifier && modelData.filter_classifier.enabled
                                                }
                                            }

                                            // Filter classifier model path
                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: Theme.spacingSM
                                                Layout.leftMargin: Theme.spacingXL
                                                visible: modelData.filter_classifier && modelData.filter_classifier.enabled
                                                Text {
                                                    text: qsTr("分类器路径:")
                                                    color: Theme.textSecondary
                                                    font.pixelSize: Theme.fontSizeXS
                                                    Layout.preferredWidth: 100
                                                }
                                                SettingsField {
                                                    Layout.fillWidth: true
                                                    configPath: "cameras." + index + ".filter_classifier.model_path"
                                                    displayValue: (modelData.filter_classifier && modelData.filter_classifier.model_path) || ""
                                                }
                                            }

                                            // Calibration normalizer
                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: Theme.spacingSM
                                                Text {
                                                    text: qsTr("校准归一化:")
                                                    color: Theme.textSecondary
                                                    font.pixelSize: Theme.fontSizeXS
                                                    Layout.preferredWidth: 120
                                                }
                                                SettingsField {
                                                    Layout.fillWidth: true
                                                    configPath: "cameras." + index + ".calibration.normalizer_path"
                                                    displayValue: (modelData.calibration && modelData.calibration.normalizer_path) || ""
                                                }
                                            }

                                            // Calibration projector
                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: Theme.spacingSM
                                                Text {
                                                    text: qsTr("校准投影:")
                                                    color: Theme.textSecondary
                                                    font.pixelSize: Theme.fontSizeXS
                                                    Layout.preferredWidth: 120
                                                }
                                                SettingsField {
                                                    Layout.fillWidth: true
                                                    configPath: "cameras." + index + ".calibration.projector_path"
                                                    displayValue: (modelData.calibration && modelData.calibration.projector_path) || ""
                                                }
                                            }

                                            Item { Layout.fillHeight: true; width: 1 }
                                        }
                                    }
                                }
                            }
                        }

                        // ── Section 1: Detection Models ──
                        ColumnLayout {
                            visible: settingsScreen.selectedIndex === 1
                            Layout.fillWidth: true
                            spacing: Theme.spacingSM

                            Text {
                                text: qsTr("每个相机的模型路径配置")
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontSizeSM
                            }

                            Repeater {
                                model: settingsScreen.readValue("cameras", [])

                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: modelContent.implicitHeight + Theme.spacingMD * 2
                                    color: Theme.cardGlass
                                    radius: Theme.radiusMD
                                    border { width: 1; color: Theme.cardGlassBorder }

                                    ColumnLayout {
                                        id: modelContent
                                        anchors.fill: parent
                                        anchors.margins: Theme.spacingMD
                                        spacing: Theme.spacingSM

                                        Text {
                                            text: modelData.camera_id || ""
                                            color: Theme.textPrimary
                                            font.pixelSize: Theme.fontSizeSM
                                            font.bold: true
                                        }

                                        // EfficientAD model
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Theme.spacingSM
                                            Text {
                                                text: qsTr("检测模型:")
                                                color: Theme.textSecondary
                                                font.pixelSize: Theme.fontSizeXS
                                                Layout.preferredWidth: 100
                                            }
                                            SettingsField {
                                                Layout.fillWidth: true
                                                configPath: "cameras." + index + ".efficientad_model_path"
                                                displayValue: modelData.efficientad_model_path || ""
                                            }
                                        }

                                        // Filter classifier
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Theme.spacingSM
                                            Text {
                                                text: qsTr("分类器:")
                                                color: Theme.textSecondary
                                                font.pixelSize: Theme.fontSizeXS
                                                Layout.preferredWidth: 100
                                            }
                                            ToggleSwitch {
                                                configPath: "cameras." + index + ".filter_classifier.enabled"
                                                checked: modelData.filter_classifier && modelData.filter_classifier.enabled
                                            }
                                            SettingsField {
                                                Layout.fillWidth: true
                                                configPath: "cameras." + index + ".filter_classifier.model_path"
                                                displayValue: (modelData.filter_classifier && modelData.filter_classifier.model_path) || ""
                                            }
                                        }

                                        // Calibration normalizer
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Theme.spacingSM
                                            Text {
                                                text: qsTr("校准归一化:")
                                                color: Theme.textSecondary
                                                font.pixelSize: Theme.fontSizeXS
                                                Layout.preferredWidth: 100
                                            }
                                            SettingsField {
                                                Layout.fillWidth: true
                                                configPath: "cameras." + index + ".calibration.normalizer_path"
                                                displayValue: (modelData.calibration && modelData.calibration.normalizer_path) || ""
                                            }
                                        }

                                        // Calibration projector
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Theme.spacingSM
                                            Text {
                                                text: qsTr("校准投影:")
                                                color: Theme.textSecondary
                                                font.pixelSize: Theme.fontSizeXS
                                                Layout.preferredWidth: 100
                                            }
                                            SettingsField {
                                                Layout.fillWidth: true
                                                configPath: "cameras." + index + ".calibration.projector_path"
                                                displayValue: (modelData.calibration && modelData.calibration.projector_path) || ""
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── Section 2: PLC Communication ──
                        ColumnLayout {
                            visible: settingsScreen.selectedIndex === 2
                            Layout.fillWidth: true
                            spacing: Theme.spacingSM

                            GridLayout {
                                columns: 2
                                rowSpacing: Theme.spacingSM
                                columnSpacing: Theme.spacingLG

                                Text { text: qsTr("PLC 状态"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                ToggleSwitch {
                                    id: plcEnabledSwitch
                                    configPath: "plc.enabled"
                                    checked: readValue("plc.enabled", false)
                                }

                                Text { text: qsTr("主机地址"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "plc.host"
                                    displayValue: readValue("plc.host", "192.168.1.100")
                                }

                                Text { text: qsTr("端口"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "plc.port"
                                    isNumeric: true
                                    displayValue: String(readValue("plc.port", 502))
                                }

                                Text { text: qsTr("缺陷线圈地址"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "plc.defect_coil"
                                    isNumeric: true
                                    displayValue: String(readValue("plc.defect_coil", 100))
                                }

                                Text { text: qsTr("停机线圈地址"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "plc.stop_coil"
                                    isNumeric: true
                                    displayValue: String(readValue("plc.stop_coil", 101))
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDefault }

                            Text {
                                text: qsTr("当前使用 ") + (plcEnabledSwitch.checked ? qsTr("Modbus TCP") : qsTr("虚拟 PLC（调试模式）"))
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSizeXS
                            }
                        }

                        // ── Section 3: Offline Platform ──
                        ColumnLayout {
                            visible: settingsScreen.selectedIndex === 3
                            Layout.fillWidth: true
                            spacing: Theme.spacingSM

                            GridLayout {
                                columns: 2
                                rowSpacing: Theme.spacingSM
                                columnSpacing: Theme.spacingLG

                                Text { text: qsTr("上传地址"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "offline_platform.upload_base_url"
                                    displayValue: readValue("offline_platform.upload_base_url", "")
                                }

                                Text { text: qsTr("热重载"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                ToggleSwitch {
                                    configPath: "offline_platform.hot_reload_enabled"
                                    checked: readValue("offline_platform.hot_reload_enabled", false)
                                }

                                Text { text: qsTr("轮询间隔"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "offline_platform.hot_reload_poll_seconds"
                                    isNumeric: true
                                    displayValue: String(readValue("offline_platform.hot_reload_poll_seconds", 30))
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDefault }

                            Text {
                                text: qsTr("模型文件变更后自动重载检测引擎，无需重启应用。")
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSizeXS
                            }
                        }

                        // ── Section 4: Alert Settings ──
                        ColumnLayout {
                            visible: settingsScreen.selectedIndex === 4
                            Layout.fillWidth: true
                            spacing: Theme.spacingSM

                            GridLayout {
                                columns: 2
                                rowSpacing: Theme.spacingSM
                                columnSpacing: Theme.spacingLG

                                Text { text: qsTr("NG 弹窗超时"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "alert.ng_popup_timeout_seconds"
                                    isNumeric: true
                                    displayValue: String(readValue("alert.ng_popup_timeout_seconds", 30))
                                }

                                Text { text: qsTr("默认动作"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsCombo {
                                    configPath: "alert.ng_default_action"
                                    items: [qsTr("自动确认缺陷"), qsTr("标记待复核")]
                                    values: ["confirm_defect", "mark_review"]
                                    currentValue: readValue("alert.ng_default_action", "confirm_defect")
                                }

                                Text { text: qsTr("声音告警"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                ToggleSwitch {
                                    configPath: "alert.sound_enabled"
                                    checked: readValue("alert.sound_enabled", false)
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDefault }

                            Text {
                                text: qsTr("超时后将自动执行默认动作。")
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSizeXS
                            }
                        }

                        // ── Section 5: Storage ──
                        ColumnLayout {
                            visible: settingsScreen.selectedIndex === 5
                            Layout.fillWidth: true
                            spacing: Theme.spacingSM

                            GridLayout {
                                columns: 2
                                rowSpacing: Theme.spacingSM
                                columnSpacing: Theme.spacingLG

                                Text { text: qsTr("日志目录"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "storage.log_dir"
                                    displayValue: readValue("storage.log_dir", "./logs")
                                }

                                Text { text: qsTr("保留天数"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "storage.log_retention_days"
                                    isNumeric: true
                                    displayValue: String(readValue("storage.log_retention_days", 30))
                                }

                                Text { text: qsTr("截图目录"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "storage.screenshot_dir"
                                    displayValue: readValue("storage.screenshot_dir", "./screenshots")
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDefault }

                            ActionButton {
                                buttonText: qsTr("清理过期日志")
                                bgColor: Theme.statusWarning
                                implicitHeight: 32
                                implicitWidth: 140
                                font.pixelSize: Theme.fontSizeXS
                                onClicked: {
                                    if (settingsScreen.viewModel) settingsScreen.viewModel.reload();
                                }
                            }
                        }

                        // ── Section 6: About ──
                        ColumnLayout {
                            visible: settingsScreen.selectedIndex === 6
                            Layout.fillWidth: true
                            spacing: Theme.spacingSM

                            Text {
                                text: qsTr("座椅缺陷在线检测系统")
                                color: Theme.textPrimary
                                font.pixelSize: Theme.fontSizeMD
                                font.bold: true
                            }

                            GridLayout {
                                columns: 2
                                rowSpacing: Theme.spacingSM
                                columnSpacing: Theme.spacingLG

                                Text { text: qsTr("产线 ID"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "app.line_id"
                                    displayValue: readValue("app.line_id", "--")
                                }

                                Text { text: qsTr("工位 ID"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsField {
                                    configPath: "app.station_id"
                                    displayValue: readValue("app.station_id", "--")
                                }

                                Text { text: qsTr("语言"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsCombo {
                                    configPath: "app.language"
                                    items: ["zh-CN", "en-US", "ja-JP"]
                                    currentValue: readValue("app.language", "zh-CN")
                                }

                                Text { text: qsTr("全屏"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                ToggleSwitch {
                                    configPath: "app.fullscreen"
                                    checked: readValue("app.fullscreen", false)
                                }

                                Text { text: qsTr("网格布局"); color: Theme.textSecondary; font.pixelSize: Theme.fontSizeSM }
                                SettingsCombo {
                                    configPath: "app.grid_layout"
                                    items: ["1x1", "1x2", "2x1", "2x2", "3x3"]
                                    currentValue: readValue("app.grid_layout", "2x2")
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderDefault }

                            Text {
                                text: qsTr("技术栈: PySide6 + QML + seat_defect_core")
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSizeXS
                            }
                            Text {
                                text: qsTr("运行环境: Python 3.12  |  Qt 6.x")
                                color: Theme.textMuted
                                font.pixelSize: Theme.fontSizeXS
                            }
                        }

                        // Bottom divider (inside Flickable content as spacer)
                        Item { Layout.fillWidth: true; height: 1 }
                    }
                }

                // ── Bottom action bar (fixed at bottom) ──
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 56
                    color: Theme.bgSecondary
                    border { width: 1; color: Theme.borderDefault }

                    RowLayout {
                        anchors.centerIn: parent
                        spacing: Theme.spacingMD

                        ActionButton {
                            buttonText: qsTr("重新加载")
                            bgColor: Theme.bgTertiary
                            implicitWidth: 120
                            font.pixelSize: Theme.fontSizeXS
                            onClicked: {
                                if (settingsScreen.viewModel) settingsScreen.viewModel.reload();
                            }
                        }

                        ActionButton {
                            buttonText: qsTr("保存所有更改")
                            bgColor: {
                                if (!settingsScreen.viewModel) return Theme.bgTertiary;
                                return settingsScreen.viewModel.isDirty ? Theme.accentGreen : Theme.bgTertiary;
                            }
                            textColor: {
                                if (!settingsScreen.viewModel) return Theme.textSecondary;
                                return settingsScreen.viewModel.isDirty ? "#000000" : Theme.textSecondary;
                            }
                            implicitWidth: 150
                            font.pixelSize: Theme.fontSizeXS
                            font.bold: true
                            onClicked: {
                                if (settingsScreen.viewModel) settingsScreen.viewModel.save();
                            }
                        }

                        ActionButton {
                            buttonText: qsTr("导入配置")
                            bgColor: Theme.bgTertiary
                            implicitWidth: 120
                            font.pixelSize: Theme.fontSizeXS
                            onClicked: importDialog.open()
                        }

                        ActionButton {
                            buttonText: qsTr("导出配置")
                            bgColor: Theme.bgTertiary
                            implicitWidth: 120
                            font.pixelSize: Theme.fontSizeXS
                            onClicked: exportDialog.open()
                        }
                    }
                }
            }
        }
    }

    // ── Toast notification (top-right corner) ──
    ToastNotification {
        id: toastNotification
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacingLG
        z: 999
    }
}
