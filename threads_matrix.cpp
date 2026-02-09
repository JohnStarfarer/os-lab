// threads_matrix.cpp

#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <algorithm>
#include <iomanip>
#include <numeric>
#include <fstream>

// прототипы
void multiply_part(const std::vector<int>& A, const std::vector<int>& B,
                   std::vector<int>& C, int n, int start_row, int end_row);
void generate_matrix(std::vector<int>& matrix, int n);
void print_submatrix(const std::vector<int>& matrix, int n);
void print_help();

int main(int argc, char* argv[]) {
    if (argc < 3) {
        print_help();
        return 1;
    }
    
    int n = std::stoi(argv[1]);
    int num_threads = std::stoi(argv[2]);
    int runs = (argc >= 4) ? std::stoi(argv[3]) : 10;
    
    if (n <= 0 || num_threads <= 0 || runs <= 0) {
        std::cerr << "Ошибка: параметры должны быть положительными числами\n";
        return 1;
    }
    
    std::cout << "МНОГОПОТОЧНОЕ УМНОЖЕНИЕ МАТРИЦ\n";
    std::cout << "Параметры:\n";
    std::cout << "  Размер матрицы: " << n << "x" << n << "\n";
    std::cout << "  Количество потоков: " << num_threads << "\n";
    std::cout << "  Количество запусков: " << runs << "\n";
    
    // выделение памяти
    std::vector<int> A(n * n);
    std::vector<int> B(n * n);
    std::vector<int> C(n * n, 0);
    
    // генерация матриц (без замера времени)
    std::srand(time(0));
    generate_matrix(A, n);
    generate_matrix(B, n);
    
    std::vector<long long> run_times;
    
    // многократные запуски
    for (int run = 1; run <= runs; run++) {
        std::fill(C.begin(), C.end(), 0); // обнуление результата
        
        auto start = std::chrono::high_resolution_clock::now();
    
        std::vector<std::thread> threads;
        int rows_per_thread = n / num_threads;
        int extra_rows = n % num_threads;
        int current_row = 0;
        
        for (int t = 0; t < num_threads; t++) {
            int start_row = current_row;
            int end_row = start_row + rows_per_thread + (t < extra_rows ? 1 : 0);
            current_row = end_row;
            
            threads.emplace_back(multiply_part, std::cref(A), std::cref(B), 
                                std::ref(C), n, start_row, end_row);
        }
        
        for (auto& thread : threads) {
            thread.join();
        }
        
        auto end = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
        
        run_times.push_back(duration.count());
        
        std::cout << "Запуск " << run << "/" << runs << ": " 
                  << duration.count() << " мс\n";
    }
    
    if (run_times.size() >= 3) {
        // удаление мин и макс значения
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
    
    std::cout << "\nЧасть результирующей матрицы (первые 5x5):\n";
    print_submatrix(C, n);
    
    return 0;
}

// умножение части матрицы
void multiply_part(const std::vector<int>& A, const std::vector<int>& B,
                   std::vector<int>& C, int n, int start_row, int end_row) {
    for (int i = start_row; i < end_row; i++) {
        for (int j = 0; j < n; j++) {
            int sum = 0;
            for (int k = 0; k < n; k++) {
                sum += A[i * n + k] * B[k * n + j];
            }
            C[i * n + j] = sum;
        }
    }
}

// ген случайной матрицы
void generate_matrix(std::vector<int>& matrix, int n) {
    for (int i = 0; i < n * n; i++) {
        matrix[i] = std::rand() % 100;
    }
}

// вывод части матрицы
void print_submatrix(const std::vector<int>& matrix, int n) {
    int size = std::min(n, 5);
    for (int i = 0; i < size; i++) {
        for (int j = 0; j < size; j++) {
            std::cout << std::setw(8) << matrix[i * n + j];
        }
        std::cout << std::endl;
    }
}

// справка
void print_help() {
    std::cout << "Использование: ./threads_matrix <размер> <потоки> [запуски]\n";
    std::cout << "  размер   - размер матрицы NxN\n";
    std::cout << "  потоки   - количество потоков\n";
    std::cout << "  запуски  - количество запусков для усреднения (по умолчанию: 10)\n";
    std::cout << "\nПример: ./threads_matrix 500 4 10\n";
}

// g++ -std=c++11 -O2 -pthread threads_matrix.cpp -o threads_matrix