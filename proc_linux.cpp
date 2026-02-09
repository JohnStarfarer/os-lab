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
#include <cmath>


void child_process(int n, int start_row, int end_row, int process_id,
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

    exit(0);
}

int main() {

    int n = 500;            
    int num_processes = 4; 

    srand(time(0));

    std::vector<int> A(n * n);
    std::vector<int> B(n * n);

    for (int i = 0; i < n * n; i++) {
        A[i] = rand() % 10;
        B[i] = rand() % 10;
    }

    size_t total_size = 3 * n * n * sizeof(int); // A + B + C

    int* shared_memory = (int*)mmap(NULL, total_size,
        PROT_READ | PROT_WRITE,
        MAP_SHARED | MAP_ANONYMOUS,
        -1, 0);

    if (shared_memory == MAP_FAILED) {
        std::cerr << "error" << std::endl;
        return 1;
    }

    int* shared_A = shared_memory;
    int* shared_B = shared_A + n * n;
    int* shared_C = shared_B + n * n;

    std::memcpy(shared_A, A.data(), n * n * sizeof(int));
    std::memcpy(shared_B, B.data(), n * n * sizeof(int));
    std::memset(shared_C, 0, n * n * sizeof(int));

    auto start_time = std::chrono::high_resolution_clock::now();

    std::vector<pid_t> pids(num_processes);
    int rows_per_process = n / num_processes;
    int extra_rows = n % num_processes;
    int current_row = 0;

    for (int p = 0; p < num_processes; p++) {
        int start_row = current_row;
        int end_row = start_row + rows_per_process;

        if (p < extra_rows) {
            end_row++;
        }
        current_row = end_row;

        pid_t pid = fork();

        if (pid == 0) {
            child_process(n, start_row, end_row, p, shared_A, shared_B, shared_C);
        }
        else if (pid > 0) {
            pids[p] = pid;
        }
        else {
            std::cerr << "error " << p << std::endl;
        }
    }

    for (int p = 0; p < num_processes; p++) {
        if (pids[p] > 0) {
            waitpid(pids[p], nullptr, 0);
        }
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);

    std::cout << "Processes!" << std::endl;
    std::cout << "Run time: " << duration.count() << " ms" << std::endl;

    munmap(shared_memory, total_size);

    return 0;
}