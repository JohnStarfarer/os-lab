// proccesses_matrix.cpp

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

int main(int argc, char* argv[]) {
    if (argc < 3) {
        print_help();
        return 1;
    }
    
    int n = std::stoi(argv[1]);
    int num_processes = std::stoi(argv[2]);
    int runs = (argc >= 4) ? std::stoi(argv[3]) : 10;
    
    if (n <= 0 || num_processes <= 0 || runs <= 0) {
        std::cerr << "Ошибка: параметры должны быть положительными числами\n";
        return 1;
    }
    
    std::cout << "МНОГОПРОЦЕССНОЕ УМНОЖЕНИЕ МАТРИЦ\n";
    std::cout << "Параметры:\n";
    std::cout << "  Размер матрицы: " << n << "x" << n << "\n";
    std::cout << "  Количество процессов: " << num_processes << "\n";
    std::cout << "  Количество запусков: " << runs << "\n";
    std::cout << "  Механизм IPC: разделяемая память (mmap)\n";
    
    std::vector<long long> run_times;
    
    for (int run = 1; run <= runs; run++) {
        size_t total_size = 3 * n * n * sizeof(int); // A + B + C
        int* shared_memory = (int*)mmap(NULL, total_size,
            PROT_READ | PROT_WRITE,
            MAP_SHARED | MAP_ANONYMOUS,
            -1, 0);
        
        if (shared_memory == MAP_FAILED) {
            std::cerr << "Ошибка выделения разделяемой памяти!\n";
            return 1;
        }
        
        // указатели на матрицы в разделяемой памяти
        int* shared_A = shared_memory;
        int* shared_B = shared_A + n * n;
        int* shared_C = shared_B + n * n;
        
        // ген матриц (без замера времени)
        std::srand(time(0));
        generate_matrix(shared_A, n);
        generate_matrix(shared_B, n);
        std::memset(shared_C, 0, n * n * sizeof(int));
        
        auto start = std::chrono::high_resolution_clock::now();
        
        std::vector<pid_t> pids(num_processes);
        int rows_per_process = n / num_processes;
        int extra_rows = n % num_processes;
        int current_row = 0;
        
        for (int p = 0; p < num_processes; p++) {
            int start_row = current_row;
            int end_row = start_row + rows_per_process;
            
            if (p < extra_rows) {
                end_row++; // распред оставшиеся строки
            }
            current_row = end_row;
            
            pid_t pid = fork();
            
            if (pid == 0) {
                // доч процесс
                child_process(n, start_row, end_row, shared_A, shared_B, shared_C);
                exit(0); // завершение доч процесса
            } else if (pid > 0) {
                // родитель
                pids[p] = pid;
            } else {
                std::cerr << "Ошибка создания процесса " << p << "\n";
                munmap(shared_memory, total_size);
                return 1;
            }
        }
        
        for (int p = 0; p < num_processes; p++) {
            if (pids[p] > 0) {
                waitpid(pids[p], nullptr, 0);
            }
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        
        run_times.push_back(duration.count());
        
        if (run == runs) {
            std::cout << "\nЧасть результирующей матрицы (первые 5x5):\n";
            print_submatrix(shared_C, n);
        }
        
        // освобождение разделяемой памяти
        munmap(shared_memory, total_size);
        
        std::cout << "Запуск " << run << "/" << runs << ": " 
                  << duration.count() << " мс\n";
    }
    
    if (run_times.size() >= 3) {
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
        
        double avg_time = (count > 0) ? static_cast<double>(sum) / count : 0;
        
        std::cout << "РЕЗУЛЬТАТЫ:\n";
        std::cout << "----------------------------------------\n";
        std::cout << "Минимальное время: " << *min_it << " мс\n";
        std::cout << "Максимальное время: " << *max_it << " мс\n";
        std::cout << "Среднее время: " << avg_time << " мс\n";
    }
    
    return 0;
}

// функция дочернего процесса
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
}

// ген случайной матрицы
void generate_matrix(int* matrix, int n) {
    for (int i = 0; i < n * n; i++) {
        matrix[i] = std::rand() % 100;
    }
}

// вывод части матрицы
void print_submatrix(int* matrix, int n) {
    int size = std::min(n, 5);
    for (int i = 0; i < size; i++) {
        for (int j = 0; j < size; j++) {
            std::cout << std::setw(8) << matrix[i * n + j];
        }
        std::cout << std::endl;
    }
}

// вывод справка
void print_help() {
    std::cout << "Использование: ./processes_matrix <размер> <процессы> [запуски]\n";
    std::cout << "  размер     - размер матрицы NxN\n";
    std::cout << "  процессы   - количество процессов\n";
    std::cout << "  запуски    - количество запусков для усреднения (по умолчанию: 10)\n";
    std::cout << "\nПример: ./processes_matrix 500 4 10\n";
}

// g++ -std=c++11 -O2 processes_matrix.cpp -o processes_matrix