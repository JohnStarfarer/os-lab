// processes_matrix.cpp
#include <iostream>
#include <vector>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <cstring>
#include <algorithm>
#include <iomanip>
#include <numeric>
#include <fstream>

// Функция дочернего процесса
void child_process(int n, int start_row, int end_row, 
                   int* shared_A, int* shared_B, int* shared_C) {
    for (int i = start_row; i < end_row; i++) {
        for (int j = 0; j < n; j++) {
            int sum = 0;
            for (int k = 0; k < n; k++) {
                sum += shared_A[i * n + k] * shared_B[k * n + j];
            }
            shared_C[i * n + j] = sum;
        }
    }
    exit(0);  // Завершаем дочерний процесс
}

// Генерация матрицы в разделяемой памяти
void generate_matrix(int* matrix, int n) {
    std::srand(static_cast<unsigned>(std::time(nullptr)));
    for (int i = 0; i < n * n; i++) {
        matrix[i] = std::rand() % 100;
    }
}

// Вывод части матрицы
void print_submatrix(int* matrix, int n, int size = 5) {
    int display_size = std::min(n, size);
    std::cout << "\nПервые " << display_size << "x" << display_size 
              << " элементов результирующей матрицы:\n";
    for (int i = 0; i < display_size; i++) {
        for (int j = 0; j < display_size; j++) {
            std::cout << std::setw(8) << matrix[i * n + j];
        }
        std::cout << std::endl;
    }
}

int main(int argc, char* argv[]) {
    // Параметры по умолчанию
    int n = 500;            // Размер матрицы
    int num_processes = 4;  // Количество процессов
    int runs = 10;          // Количество запусков
    
    // Парсинг аргументов командной строки
    if (argc >= 2) n = std::stoi(argv[1]);
    if (argc >= 3) num_processes = std::stoi(argv[2]);
    if (argc >= 4) runs = std::stoi(argv[3]);
    
    if (num_processes <= 0 || n <= 0 || runs <= 0) {
        std::cerr << "Ошибка: все параметры должны быть положительными числами\n";
        return 1;
    }
    
    std::cout << "========================================\n";
    std::cout << "МНОГОПРОЦЕССНОЕ УМНОЖЕНИЕ МАТРИЦ\n";
    std::cout << "========================================\n";
    std::cout << "Размер матрицы: " << n << "x" << n << " (элементов: " << n*n << ")\n";
    std::cout << "Количество процессов: " << num_processes << "\n";
    std::cout << "Количество запусков для усреднения: " << runs << "\n";
    std::cout << "Механизм IPC: Разделяемая память (mmap)\n";
    std::cout << "========================================\n";
    
    std::vector<long long> run_times(runs);
    
    for (int run = 0; run < runs; run++) {
        // Выделение разделяемой памяти для матриц A, B, C
        size_t total_size = 3 * n * n * sizeof(int);
        int* shared_memory = (int*)mmap(NULL, total_size,
            PROT_READ | PROT_WRITE,
            MAP_SHARED | MAP_ANONYMOUS,
            -1, 0);
        
        if (shared_memory == MAP_FAILED) {
            std::cerr << "Ошибка выделения разделяемой памяти!" << std::endl;
            return 1;
        }
        
        // Указатели на матрицы в разделяемой памяти
        int* shared_A = shared_memory;
        int* shared_B = shared_A + n * n;
        int* shared_C = shared_B + n * n;
        
        // Генерация исходных матриц
        generate_matrix(shared_A, n);
        generate_matrix(shared_B, n);
        std::memset(shared_C, 0, n * n * sizeof(int));
        
        // Засекаем время умножения
        auto start_time = std::chrono::high_resolution_clock::now();
        
        // Создание дочерних процессов
        std::vector<pid_t> pids(num_processes);
        int rows_per_process = n / num_processes;
        int extra_rows = n % num_processes;
        int current_row = 0;
        
        for (int p = 0; p < num_processes; p++) {
            int start_row = current_row;
            int end_row = start_row + rows_per_process;
            
            if (p < extra_rows) {
                end_row++;  // Распределяем оставшиеся строки
            }
            current_row = end_row;
            
            pid_t pid = fork();
            
            if (pid == 0) {
                // Дочерний процесс
                child_process(n, start_row, end_row, shared_A, shared_B, shared_C);
                // child_process завершается с exit(0)
            } else if (pid > 0) {
                // Родительский процесс сохраняет PID
                pids[p] = pid;
            } else {
                std::cerr << "Ошибка создания процесса " << p << std::endl;
                munmap(shared_memory, total_size);
                return 1;
            }
        }
        
        // Родительский процесс ожидает завершения всех дочерних
        for (int p = 0; p < num_processes; p++) {
            if (pids[p] > 0) {
                waitpid(pids[p], nullptr, 0);
            }
        }
        
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
            end_time - start_time);
        
        run_times[run] = duration.count();
        
        // Вывод части результата на последнем запуске
        if (run == runs - 1) {
            print_submatrix(shared_C, n);
        }
        
        // Освобождение разделяемой памяти
        munmap(shared_memory, total_size);
        
        std::cout << "Запуск " << run + 1 << "/" << runs 
                  << ": " << duration.count() << " мс\n";
    }
    
    // Усреднение результатов
    double avg_time = 0;
    if (runs >= 3) {
        auto min_it = std::min_element(run_times.begin(), run_times.end());
        auto max_it = std::max_element(run_times.begin(), run_times.end());
        
        long long sum = 0;
        int count = 0;
        for (auto time : run_times) {
            if (time != *min_it && time != *max_it) {
                sum += time;
                count++;
            }
        }
        
        avg_time = (count > 0) ? static_cast<double>(sum) / count : 0;
        
        std::cout << "\n========================================\n";
        std::cout << "РЕЗУЛЬТАТЫ ИЗМЕРЕНИЙ:\n";
        std::cout << "Минимальное время: " << *min_it << " мс\n";
        std::cout << "Максимальное время: " << *max_it << " мс\n";
        std::cout << "Среднее время (без min/max): " << avg_time << " мс\n";
        std::cout << "Погрешность: ±" << (*max_it - *min_it) / 2.0 << " мс\n";
    } else {
        avg_time = std::accumulate(run_times.begin(), run_times.end(), 0.0) / runs;
        std::cout << "\nСреднее время: " << avg_time << " мс\n";
    }
    
    // Сохранение результата в файл
    std::ofstream outfile("processes_result.txt", std::ios::app);
    if (outfile.is_open()) {
        outfile << n << " " << num_processes << " " << avg_time << "\n";
        outfile.close();
    }
    
    std::cout << "\n========================================\n";
    std::cout << "Результат сохранен в файл: processes_result.txt\n";
    std::cout << "Формат: <размер_матрицы> <количество_процессов> <время_мс>\n";
    std::cout << "========================================\n";
    
    return 0;
}