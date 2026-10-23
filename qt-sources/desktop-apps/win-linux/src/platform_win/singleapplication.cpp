/*
 * (c) Copyright Ascensio System SIA 2010-2019
 *
 * This program is a free software product. You can redistribute it and/or
 * modify it under the terms of the GNU Affero General Public License (AGPL)
 * version 3 as published by the Free Software Foundation. In accordance with
 * Section 7(a) of the GNU AGPL its Section 15 shall be amended to the effect
 * that Ascensio System SIA expressly excludes the warranty of non-infringement
 * of any third-party rights.
 *
 * This program is distributed WITHOUT ANY WARRANTY; without even the implied
 * warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR  PURPOSE. For
 * details, see the GNU AGPL at: http://www.gnu.org/licenses/agpl-3.0.html
 *
 * You can contact Ascensio System SIA at 20A-12 Ernesta Birznieka-Upisha
 * street, Riga, Latvia, EU, LV-1050.
 *
 * The  interactive user interfaces in modified source and object code versions
 * of the Program must display Appropriate Legal Notices, as required under
 * Section 5 of the GNU AGPL version 3.
 *
 * Pursuant to Section 7(b) of the License you must retain the original Product
 * logo when distributing the program. Pursuant to Section 7(e) we decline to
 * grant you any rights under trademark law for use of our trademarks.
 *
 * All the Product's GUI elements, including illustrations and icon sets, as
 * well as technical writing content are licensed under the terms of the
 * Creative Commons Attribution-ShareAlike 4.0 International. See the License
 * terms at http://creativecommons.org/licenses/by-sa/4.0/legalcode
 *
 */

#include <windowsx.h>
#include "cascapplicationmanagerwrapper.h"
#include "singleapplication.h"
#include "defines.h"
#include <QThread>
#include <QCryptographicHash>
#include <QFileInfo>

#define RECEIVER_WINDOW WINDOW_CLASS_NAME
#define RETRIES_COUNT 10
#define RETRIES_DELAY_MS 500


SingleApplication::SingleApplication(int &argc, char *argv[]) :
    QApplication(argc, argv),
    m_isPrimary(false),
    m_hWnd(nullptr),
    m_hMutex(nullptr)
{
    // Qingliang community, 2026-10-23: separate explicit settings profiles from the regular instance.
    m_receiverClass = QString::fromWCharArray(RECEIVER_WINDOW);
    QString mutexName = QStringLiteral(APP_MUTEX_NAME);
    const QString settingsFile = qEnvironmentVariable("QINGLIANG_SETTINGS_FILE");
    if (!settingsFile.isEmpty() && QDir::isAbsolutePath(settingsFile)) {
        const QString key = QDir::cleanPath(QDir::fromNativeSeparators(QFileInfo(settingsFile).absoluteFilePath())).toCaseFolded();
        const QString suffix = "." + QString::fromLatin1(QCryptographicHash::hash(key.toUtf8(), QCryptographicHash::Sha256).toHex().left(24));
        mutexName += suffix;
        m_receiverClass += suffix;
    }
    m_hMutex = CreateMutexW(NULL, FALSE, mutexName.toStdWString().c_str());
    if (m_hMutex && GetLastError() != ERROR_ALREADY_EXISTS) {
        m_isPrimary = true;
        startPrimary();
    }
}

SingleApplication::~SingleApplication()
{
    if (m_hMutex != nullptr)
        CloseHandle(m_hMutex);

    if (m_hWnd)
        DestroyWindow(m_hWnd);
}

bool SingleApplication::isPrimary() const
{
    return m_isPrimary;
}

bool SingleApplication::sendMessage(const QByteArray &message)
{
    if (m_isPrimary)
        return false;

    HWND hwnd = NULL;
    int retries = RETRIES_COUNT;
    do {
        // The receiver is an HWND_MESSAGE window, not a top-level editor window.
        hwnd = FindWindowExW(HWND_MESSAGE, NULL, m_receiverClass.toStdWString().c_str(), NULL);
        if (hwnd) break;
        QThread::msleep(RETRIES_DELAY_MS);
    } while (retries-- > 0);

    if (hwnd != NULL) {
        QString msg(message);
        wchar_t *cm_line = new wchar_t[msg.length() + 1];
        msg.toWCharArray(cm_line);
        cm_line[msg.length()] = '\0';

        COPYDATASTRUCT MyCDS = {1};
        MyCDS.cbData = sizeof(WCHAR) * (wcslen(cm_line) + 1);
        MyCDS.lpData = cm_line;
        DWORD_PTR response = 0;
        const bool sent = SendMessageTimeoutW(hwnd, WM_COPYDATA, WPARAM(0), LPARAM((LPVOID)&MyCDS),
                                             SMTO_ABORTIFHUNG | SMTO_BLOCK, 2000, &response) != 0;
        delete[] cm_line;
        return sent && response != 0;
    }
    return false;
}

void SingleApplication::startPrimary()
{
    HINSTANCE hInstance = GetModuleHandle(nullptr);
    WNDCLASSEX wcx{sizeof(WNDCLASSEX)};
    wcx.hInstance = hInstance;
    wcx.lpfnWndProc = WndProc;
    const std::wstring receiverClass = m_receiverClass.toStdWString();
    wcx.lpszClassName = receiverClass.c_str();
    RegisterClassEx(&wcx);

    m_hWnd = CreateWindowExW(0, receiverClass.c_str(), nullptr, 0, 0, 0, 0, 0, HWND_MESSAGE, nullptr, hInstance, nullptr);
    SetWindowLongPtr(m_hWnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(this));
}

void SingleApplication::invokeSignal(const QString &data)
{
    emit receivedMessage(data.toUtf8());
}

LRESULT SingleApplication::WndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    SingleApplication *app = reinterpret_cast<SingleApplication*>(GetWindowLongPtr(hWnd, GWLP_USERDATA));
    if (!app)
        return DefWindowProc(hWnd, msg, wParam, lParam);

    switch (msg) {
    case WM_COPYDATA: {
        COPYDATASTRUCT* pcds = (COPYDATASTRUCT*)lParam;
        if (pcds && pcds->dwData == 1 && pcds->lpData && pcds->cbData >= sizeof(WCHAR) && pcds->cbData % sizeof(WCHAR) == 0) {
            const WCHAR* text = static_cast<const WCHAR*>(pcds->lpData);
            const int count = static_cast<int>(pcds->cbData / sizeof(WCHAR));
            if (text[count - 1] != L'\0') return FALSE;
            QMetaObject::invokeMethod(app, "invokeSignal", Qt::QueuedConnection, Q_ARG(QString, QString::fromWCharArray(text, count - 1)));
            return TRUE;
        }
        return FALSE;
    }
    case UM_INSTALL_UPDATE: {
        QTimer::singleShot(500, []() {
            AscAppManager::closeAppWindows();
        });
        break;
    }
    default:
        break;
    }
    return DefWindowProc(hWnd, msg, wParam, lParam);
}
