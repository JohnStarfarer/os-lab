// lab3_linux.cpp
#include <iostream>
#include <fstream>
#include <vector>
#include <random>
#include <chrono>
#include <cstring>
#include <algorithm>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <thread>
#include <cstdlib>
#include <cmath>

// Функция для очистки page cache (требует sudo)
void clear_page_cache() {
    std::cout << "Очистка page cache..." << std::endl;
    int result = system("sudo sync && sudo echo 3 > /proc/sys/vm/drop_caches");
    if (result != 0) {
        std::cerr << "Предупреждение: не удалось очистить page cache!" << std::endl;
        std::cerr << "Для получения major faults запустите программу с sudo" << std::endl;
    } else {
        std::cout << "Page cache очищен" << std::endl;
    }
    sleep(1); // Даем время системе
}

// Получение статистики page faults из /proc/self/stat
void get_page_faults(unsigned long long& minflt, unsigned long long& majflt) {
    FILE* f = fopen("/proc/self/stat", "r");
    if (!f) {
        minflt = majflt = 0;
        return;
    }
    
    // Формат /proc/self/stat: pid comm state ppid pgrp ... minflt majflt ...
    // Нам нужны поля 10 (minflt) и 12 (majflt)
    unsigned long long pid;
    char comm[256];
    char state;
    
    // Считываем первые 13 полей
    if (fscanf(f, "%llu %s %c %*d %*d %*d %*d %*d %*u %llu %*u %llu", 
               &pid, comm, &state, &minflt, &majflt) != 5) {
        minflt = majflt = 0;
    }
    
    fclose(f);
}

// Создание файла со случайными данными
bool create_random_file(const std::string& filename, size_t file_size) {
    std::ofstream file(filename, std::ios::binary | std::ios::out);
    if (!file) {
        std::cerr << "Ошибка создания файла: " << filename << std::endl;
        return false;
    }
    
    std::cout << "Создание файла " << filename << " размером " 
              << file_size / (1024*1024) << " MB... ";
    std::cout.flush();
    
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<int> dist(0, 255);
    
    const size_t BUFFER_SIZE = 1024 * 1024; // 1 MB
    std::vector<char> buffer(BUFFER_SIZE);
    
    for (size_t i = 0; i < file_size; i += BUFFER_SIZE) {
        size_t chunk_size = std::min(BUFFER_SIZE, file_size - i);
        
        for (size_t j = 0; j < chunk_size; ++j) {
            buffer[j] = static_cast<char>(dist(gen));
        }
        
        file.write(buffer.data(), chunk_size);
    }
    
    file.close();
    std::cout << "Готово!" << std::endl;
    return true;
}

// Генерация случайного порядка страниц
std::vector<size_t> generate_random_pages(size_t total_pages, size_t pages_to_access) {
    std::vector<size_t> pages(total_pages);
    
    for (size_t i = 0; i < total_pages; ++i) {
        pages[i] = i;
    }
    
    std::random_device rd;
    std::mt19937 gen(rd());
    std::shuffle(pages.begin(), pages.end(), gen);
    
    pages.resize(pages_to_access);
    return pages;
}

// Измерение производительности с mmap
void test_mmap_performance(const std::string& filename, 
                          size_t file_size = 100 * 1024 * 1024,  // 100 MB
                          size_t page_size = 4096,               // 4 KB
                          size_t pages_to_access = 1000,
                          size_t num_runs = 5) {
    
    std::cout << "\n=== Настройки теста ===" << std::endl;
    std::cout << "Размер файла: " << file_size / (1024*1024) << " MB" << std::endl;
    std::cout << "Размер страницы: " << page_size / 1024 << " KB" << std::endl;
    std::cout << "Страниц для доступа: " << pages_to_access << std::endl;
    std::cout << "Количество запусков: " << num_runs << std::endl;
    
    // Генерация случайного порядка страниц
    size_t total_pages = file_size / page_size;
    auto page_order = generate_random_pages(total_pages, pages_to_access);
    
    // Статистика
    struct Stats {
        double first_time = 0;
        double second_time = 0;
        unsigned long long first_minflt = 0;
        unsigned long long first_majflt = 0;
        unsigned long long second_minflt = 0;
        unsigned long long second_majflt = 0;
    } total_stats;
    
    // Основной цикл тестов
    for (size_t run = 0; run < num_runs; ++run) {
        std::cout << "\n=== Запуск " << (run + 1) << " из " << num_runs << " ===" << std::endl;
        
        // Очистка кэша перед первым запуском
        if (run == 0) {
            clear_page_cache();
        }
        
        // Открытие файла
        int fd = open(filename.c_str(), O_RDONLY);
        if (fd == -1) {
            std::cerr << "Ошибка открытия файла: " << strerror(errno) << std::endl;
            return;
        }
        
        // Отображение файла в память
        void* mapped_data = mmap(nullptr, file_size, PROT_READ, MAP_PRIVATE, fd, 0);
        if (mapped_data == MAP_FAILED) {
            std::cerr << "Ошибка mmap: " << strerror(errno) << std::endl;
            close(fd);
            return;
        }
        
        // Совет системе о паттерне доступа
        madvise(mapped_data, file_size, MADV_RANDOM);
        
        char* data = static_cast<char*>(mapped_data);
        volatile char temp; // volatile чтобы компилятор не оптимизировал чтение
        
        // === ПЕРВОЕ ОБРАЩЕНИЕ ===
        unsigned long long minflt_before, majflt_before;
        unsigned long long minflt_after, majflt_after;
        
        get_page_faults(minflt_before, majflt_before);
        auto start = std::chrono::high_resolution_clock::now();
        
        // Обращение к страницам в случайном порядке
        for (size_t page_idx : page_order) {
            size_t offset = page_idx * page_size;
            temp = data[offset]; // Чтение первого байта страницы
            // Можно прочитать больше байт для полного доступа к странице
            for (size_t i = 0; i < 64; i += 8) {
                temp = data[offset + i];
            }
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        get_page_faults(minflt_after, majflt_after);
        
        auto duration_first = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
        unsigned long long first_minflt = minflt_after - minflt_before;
        unsigned long long first_majflt = majflt_after - majflt_before;
        
        // === ВТОРОЕ ОБРАЩЕНИЕ (к тем же страницам) ===
        get_page_faults(minflt_before, majflt_before);
        start = std::chrono::high_resolution_clock::now();
        
        for (size_t page_idx : page_order) {
            size_t offset = page_idx * page_size;
            temp = data[offset];
            for (size_t i = 0; i < 64; i += 8) {
                temp = data[offset + i];
            }
        }
        
        end = std::chrono::high_resolution_clock::now();
        get_page_faults(minflt_after, majflt_after);
        
        auto duration_second = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
        unsigned long long second_minflt = minflt_after - minflt_before;
        unsigned long long second_majflt = majflt_after - majflt_before;
        
        // Освобождение ресурсов
        munmap(mapped_data, file_size);
        close(fd);
        
        // Вывод результатов текущего запуска
        std::cout << "Первое обращение:" << std::endl;
        std::cout << "  Время: " << duration_first << " мкс" << std::endl;
        std::cout << "  Minor faults: " << first_minflt << std::endl;
        std::cout << "  Major faults: " << first_majflt << std::endl;
        
        std::cout << "Второе обращение:" << std::endl;
        std::cout << "  Время: " << duration_second << " мкс" << std::endl;
        std::cout << "  Minor faults: " << second_minflt << std::endl;
        std::cout << "  Major faults: " << second_majflt << std::endl;
        
        double speedup = static_cast<double>(duration_first) / duration_second;
        std::cout << "Ускорение: " << speedup << "x" << std::endl;
        
        // Накопление статистики
        total_stats.first_time += duration_first;
        total_stats.second_time += duration_second;
        total_stats.first_minflt += first_minflt;
        total_stats.first_majflt += first_majflt;
        total_stats.second_minflt += second_minflt;
        total_stats.second_majflt += second_majflt;
        
        // Пауза между запусками (если не последний)
        if (run < num_runs - 1) {
            std::cout << "Пауза 1 секунда..." << std::endl;
            sleep(1);
        }
    }
    
    // Вывод средних результатов
    std::cout << "\n=== СРЕДНИЕ РЕЗУЛЬТАТЫ (" << num_runs << " запусков) ===" << std::endl;
    std::cout << "\nПЕРВОЕ ОБРАЩЕНИЕ:" << std::endl;
    std::cout << "  Среднее время: " << total_stats.first_time / num_runs << " мкс" << std::endl;
    std::cout << "  Средние Minor faults: " << total_stats.first_minflt / num_runs << std::endl;
    std::cout << "  Средние Major faults: " << total_stats.first_majflt / num_runs << std::endl;
    
    std::cout << "\nВТОРОЕ ОБРАЩЕНИЕ:" << std::endl;
    std::cout << "  Среднее время: " << total_stats.second_time / num_runs << " мкс" << std::endl;
    std::cout << "  Средние Minor faults: " << total_stats.second_minflt / num_runs << std::endl;
    std::cout << "  Средние Major faults: " << total_stats.second_majflt / num_runs << std::endl;
    
    double avg_speedup = (total_stats.first_time / total_stats.second_time);
    std::cout << "\nСреднее ускорение: " << avg_speedup << "x" << std::endl;
    
    // Анализ производительности
    std::cout << "\n=== АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ ===" << std::endl;
    if (total_stats.first_majflt > 0) {
        std::cout << "✓ Major faults обнаружены (страницы загружались с диска)" << std::endl;
    } else {
        std::cout << "⚠ Major faults не обнаружены. Запустите с sudo для очистки кэша" << std::endl;
    }
    
    if (avg_speedup > 1.5) {
        std::cout << "✓ Значительное ускорение при повторном обращении" << std::endl;
        std::cout << "  Причина: страницы закэшированы в оперативной памяти" << std::endl;
    }
    
    // Расчет времени на страницу
    double avg_time_per_page_first = (total_stats.first_time / num_runs) / pages_to_access;
    double avg_time_per_page_second = (total_stats.second_time / num_runs) / pages_to_access;
    std::cout << "\nСреднее время доступа к странице:" << std::endl;
    std::cout << "  Первое обращение: " << avg_time_per_page_first << " мкс/страницу" << std::endl;
    std::cout << "  Второе обращение: " << avg_time_per_page_second << " мкс/страницу" << std::endl;
}

int main() {
    std::cout << "==========================================" << std::endl;
    std::cout << "Лабораторная работа №3: Виртуальная память" << std::endl;
    std::cout << "Изучение mmap и page faults в Linux" << std::endl;
    std::cout << "==========================================" << std::endl;
    
    // Параметры
    const std::string filename = "test_data_100mb.bin";
    const size_t FILE_SIZE = 100 * 1024 * 1024;    // 100 MB
    const size_t PAGE_SIZE = 4096;                 // 4 KB
    const size_t PAGES_TO_ACCESS = 1000;
    const size_t NUM_RUNS = 5;
    
    try {
        // 1. Создание файла со случайными данными
        std::cout << "\n[1] Подготовка тестового файла..." << std::endl;
        if (!create_random_file(filename, FILE_SIZE)) {
            return 1;
        }
        
        // 2. Проверка размера файла
        struct stat file_stat;
        if (stat(filename.c_str(), &file_stat) == 0) {
            std::cout << "Файл создан. Размер: " << file_stat.st_size / (1024*1024) << " MB" << std::endl;
        }
        
        // 3. Выполнение тестов производительности
        std::cout << "\n[2] Запуск тестов производительности..." << std::endl;
        test_mmap_performance(filename, FILE_SIZE, PAGE_SIZE, PAGES_TO_ACCESS, NUM_RUNS);
        
        // 4. Удаление временного файла
        std::cout << "\n[3] Очистка..." << std::endl;
        if (remove(filename.c_str()) == 0) {
            std::cout << "Файл " << filename << " удален" << std::endl;
        } else {
            std::cerr << "Не удалось удалить файл: " << filename << std::endl;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Ошибка: " << e.what() << std::endl;
        return 1;
    }
    
    std::cout << "\n==========================================" << std::endl;
    std::cout << "Лабораторная работа завершена!" << std::endl;
    std::cout << "==========================================" << std::endl;
    
    return 0;
}

// g++ -std=c++17 -O2 -o page page.cpp