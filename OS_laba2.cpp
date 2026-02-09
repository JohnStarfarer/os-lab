#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <cstdlib>

void fill_matrix(std::vector<std::vector<int>>& matrix_a, std::vector<std::vector<int>>& matrix_b, int n) {
    int r1 = 0, r2 = 0;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            r1 = rand() % 10;
            r2 = rand() % 10;
            matrix_a[i][j] = r1;
            matrix_b[i][j] = r2;
        }
    }
}

void multiply_part(const std::vector<std::vector<int>>& A, const std::vector<std::vector<int>>& B,
    std::vector<std::vector<int>>& C, int start_row, int end_row) {

    int n = A.size();
    for (int i = start_row; i < end_row; i++) {
        for (int j = 0; j < n; j++) {
            int sum = 0;
            for (int k = 0; k < n; k++) {
                sum += A[i][k] * B[k][j];
            }
            C[i][j] = sum;
        }
    }
}

void multiply_matrices(const std::vector<std::vector<int>>& A,
    const std::vector<std::vector<int>>& B,
    int num_threads) {

    int n = A.size();
    std::vector<std::vector<int>> C(n, std::vector<int>(n, 0));

    std::vector<std::thread> threads;

    int rows_per_thread = n / num_threads;
    int extra_rows = n % num_threads;
    int current_row = 0;

    for (int t = 0; t < num_threads; t++) {
        int start = current_row;
        int end = start + rows_per_thread + (t < extra_rows ? 1 : 0);
        current_row = end;

        threads.emplace_back(multiply_part, std::cref(A), std::cref(B), std::ref(C), start, end);
    }

    for (auto& thread : threads) {
        thread.join();
    }


}

int main() {

    int n = 500;
    int num_threads = 1;
    std::vector<std::vector<int>> A(n, std::vector<int>(n));
    std::vector<std::vector<int>> B(n, std::vector<int>(n));

    srand(time(0));
    fill_matrix(A, B, n);

    auto start = std::chrono::high_resolution_clock::now();
    multiply_matrices(A, B, num_threads);
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);

    std::cout << "Threads!" << std::endl;
    std::cout << "Run time: " << duration.count() << " ms" << std::endl;
}
