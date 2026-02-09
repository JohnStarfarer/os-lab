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

// Функция для умножения части матрицы
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

// Генерация случайной матрицы
void generate_matrix(std::vector<int>& matrix, int n) {
    std::srand(static_cast<unsigned>(std::time(nullptr)));
    for (int i = 0; i < n * n; i++) {
        matrix[i] = std::rand() % 100;  // Числа от 0 до 99
    }
}

// Вывод части матрицы для проверки
void print_submatrix(const std::vector<int>& matrix, int n, int size = 5) {
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

// Проверка правильности умножения (опционально, для тестов)
bool verify_correctness(const std::vector<int>& A, const std::vector<int>& B,
                        const std::vector<int>& C, int n) {
    std::vector<int> test_C(n * n, 0);
    
    // Умножение в одном потоке для проверки
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            int sum = 0;
            for (int k = 0; k < n; k++) {
                sum += A[i * n + k] * B[k * n + j];
            }
            test_C[i * n + j] = sum;
        }
    }
    
    return C == test_C;
}

int main(int argc, char* argv[]) {
    // Параметры по умолчанию
    int n = 500;          // Размер матрицы
    int num_threads = 4;  // Количество потоков
    int runs = 10;        // Количество запусков для усреднения
    
    // Парсинг аргументов командной строки
    if (argc >= 2) n = std::stoi(argv[1]);
    if (argc >= 3) num_threads = std::stoi(argv[2]);
    if (argc >= 4) runs = std::stoi(argv[3]);
    
    if (num_threads <= 0 || n <= 0 || runs <= 0) {
        std::cerr << "Ошибка: все параметры должны быть положительными числами\n";
        return 1;
    }
    
    std::cout << "========================================\n";
    std::cout << "МНОГОПОТОЧНОЕ УМНОЖЕНИЕ МАТРИЦ\n";
    std::cout << "========================================\n";
    std::cout << "Размер матрицы: " << n << "x" << n << " (элементов: " << n*n << ")\n";
    std::cout << "Количество потоков: " << num_threads << "\n";
    std::cout << "Количество запусков для усреднения: " << runs << "\n";
    std::cout << "========================================\n";
    
    // Выделение памяти для матриц
    std::vector<int> A(n * n);
    std::vector<int> B(n * n);
    std::vector<int> C(n * n);
    
    // Генерация матриц A и B
    std::cout << "\nГенерация матриц... ";
    generate_matrix(A, n);
    generate_matrix(B, n);
    std::cout << "Готово!\n";
    
    std::vector<long long> run_times(runs);
    
    // Многократный запуск для усреднения
    for (int run = 0; run < runs; run++) {
        // Обнуляем результирующую матрицу
        std::fill(C.begin(), C.end(), 0);
        
        // Засекаем время ТОЛЬКО умножения
        auto start_time = std::chrono::high_resolution_clock::now();
        
        // Создаем и запускаем потоки
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
        
        // Ожидаем завершения всех потоков
        for (auto& thread : threads) {
            thread.join();
        }
        
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
            end_time - start_time);
        
        run_times[run] = duration.count();
        
        // Прогресс выполнения
        std::cout << "Запуск " << run + 1 << "/" << runs 
                  << ": " << duration.count() << " мс\n";
    }
    
    // Усреднение результатов (удаляем минимальное и максимальное значения)
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
    
    // Проверка правильности (опционально)
    if (n <= 200) {  // Проверяем только для небольших матриц
        std::cout << "\nПроверка правильности вычислений... ";
        if (verify_correctness(A, B, C, n)) {
            std::cout << "ВСЕ ВЕРНО!\n";
        } else {
            std::cout << "ОШИБКА!\n";
        }
    }
    
    // Вывод части результата
    print_submatrix(C, n);
    
    // Сохранение результата в файл (для построения графиков)
    std::ofstream outfile("threads_result.txt", std::ios::app);
    if (outfile.is_open()) {
        outfile << n << " " << num_threads << " " << avg_time << "\n";
        outfile.close();
    }
    
    std::cout << "\n========================================\n";
    std::cout << "Результат сохранен в файл: threads_result.txt\n";
    std::cout << "Формат: <размер_матрицы> <количество_потоков> <время_мс>\n";
    std::cout << "========================================\n";
    
    return 0;
}