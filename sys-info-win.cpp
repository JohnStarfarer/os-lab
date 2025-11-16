//x86_64-w64-mingw32-g++ -o sys-info-win.exe sys-info-win.cpp -lpsapi -lnetapi32
#include <windows.h>
#include <stdio.h>
#include <tchar.h>
#include <psapi.h>
#include <versionhelpers.h>
#include <lm.h>

#pragma comment(lib, "psapi.lib")

void OS() {
    printf("Версия операционной системы:\n");
    
    if (IsWindows10OrGreater()) {
        printf("Windows 10 или новее\n");
    } else {
        printf("Старая версия Windows\n");
    }
    printf("\n");
}

void Mem() {   
    MEMORYSTATUSEX memInfo;
    memInfo.dwLength = sizeof(MEMORYSTATUSEX);
    
    if (GlobalMemoryStatusEx(&memInfo)) {
        printf("Физическая память:\n");
        printf("\tдоступно: %.2f GB\n", (double)memInfo.ullAvailPhys / (1024 * 1024 * 1024));
        printf("\tвсего: %.2f GB\n", (double)memInfo.ullTotalPhys / (1024 * 1024 * 1024));
        printf("\tиспользование: %ld%%\n", memInfo.dwMemoryLoad);
        
        printf("Виртуальная память:\n");
        printf("\tдоступно: %.2f GB\n", (double)memInfo.ullAvailVirtual / (1024 * 1024 * 1024));
        printf("\tвсего: %.2f GB\n", (double)memInfo.ullTotalVirtual / (1024 * 1024 * 1024));
    }

    PERFORMANCE_INFORMATION perfInfo;
    perfInfo.cb = sizeof(PERFORMANCE_INFORMATION);
    
    if (GetPerformanceInfo(&perfInfo, sizeof(PERFORMANCE_INFORMATION))) {
        printf("Размер файла подкачки: %.2f GB\n", 
               (double)(perfInfo.PageSize * perfInfo.CommitLimit) / (1024 * 1024 * 1024));
    }
    printf("\n");
}

void Proc() {
    
    SYSTEM_INFO sysInfo;
    GetSystemInfo(&sysInfo);
    
    printf("Количество ядер процессора: %lu\n", sysInfo.dwNumberOfProcessors);
    
    printf("Архитектура процессора: ");
    switch (sysInfo.wProcessorArchitecture) {
        case PROCESSOR_ARCHITECTURE_AMD64:
            printf("x64 (AMD или Intel)\n");
            break;
        case PROCESSOR_ARCHITECTURE_ARM:
            printf("ARM\n");
            break;
        case PROCESSOR_ARCHITECTURE_ARM64:
            printf("ARM64\n");
            break;
        case PROCESSOR_ARCHITECTURE_IA64:
            printf("Intel Itanium\n");
            break;
        case PROCESSOR_ARCHITECTURE_INTEL:
            printf("x86\n");
            break;
        default:
            printf("Неизвестная архитектура\n");
    }
    printf("\n");
}

void PC() {
    TCHAR computerName[MAX_COMPUTERNAME_LENGTH + 1];
    DWORD size = sizeof(computerName) / sizeof(TCHAR);
    
    if (GetComputerName(computerName, &size)) {
        _tprintf(_T("Имя компьютера: %s\n"), computerName);
    }
    
    TCHAR userName[256];
    DWORD userNameSize = sizeof(userName) / sizeof(TCHAR);
    
    if (GetUserName(userName, &userNameSize)) {
        _tprintf(_T("Имя пользователя: %s\n"), userName);
    }
    printf("\n");
}

void LogicDiscs() {

}

int main() {
    SetConsoleOutputCP(65001);
  
    OS();
    Mem();
    Proc();
    PC();
    LogicDiscs();
    
    printf("Нажмите любую клавишу для выхода...");
    getchar();
    
    return 0;
}