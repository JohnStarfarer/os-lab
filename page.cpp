#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <random>
#include <chrono>
#include <cstring>

// Чтение page faults из /proc/self/stat
void readPageFaults(unsigned long& minflt, unsigned long& majflt) {
    FILE* f = fopen("/proc/self/stat", "r");
    if (f) {
        // Поля 10 и 12 — minflt и majflt
        fscanf(f, "%*d %*s %*c %*d %*d %*d %*d %*d %*u %*u %*u %*u %*u %lu %lu", &minflt, &majflt);
        fclose(f);
    }
}

int main() {
    // Создание файла, mmap, тесты...
    unsigned long minflt1, majflt1, minflt2, majflt2;
    readPageFaults(minflt1, majflt1);
    // Первое обращение
    readPageFaults(minflt2, majflt2);
    std::cout << "Major faults: " << majflt2 - majflt1 << ", Minor faults: " << minflt2 - minflt1 << std::endl;
    // Очистка кэша (требует sudo):
    // system("echo 3 > /proc/sys/vm/drop_caches");
    return 0;
}