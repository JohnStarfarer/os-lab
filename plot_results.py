#!/usr/bin/env python3
# plot_results.py - построение графиков для лабораторной работы

import matplotlib.pyplot as plt
import numpy as np
import os
from datetime import datetime

# Создаем директорию для графиков
os.makedirs('graphs', exist_ok=True)

def read_results(filename):
    """Чтение результатов из файла"""
    data = {}
    try:
        with open(filename, 'r') as f:
            for line in f:
                if line.strip():
                    n, workers, time = map(float, line.strip().split())
                    n, workers = int(n), int(workers)
                    if n not in data:
                        data[n] = {}
                    if workers not in data[n]:
                        data[n][workers] = []
                    data[n][workers].append(time)
    except FileNotFoundError:
        print(f"Файл {filename} не найден!")
    return data

def plot_threads_vs_processes():
    """Сравнение потоков и процессов"""
    threads_data = read_results('threads_result.txt')
    processes_data = read_results('processes_result.txt')
    
    if not threads_data or not processes_data:
        print("Недостаточно данных для сравнения!")
        return
    
    # Берем первый размер матрицы, для которого есть данные
    n = list(threads_data.keys())[0]
    
    if n not in processes_data:
        print(f"Нет данных для матрицы {n}x{n} в процессах!")
        return
    
    # Подготовка данных
    workers = sorted(threads_data[n].keys())
    thread_times = [np.mean(threads_data[n][w]) for w in workers]
    process_times = [np.mean(processes_data[n][w]) for w in workers if w in processes_data[n]]
    
    # Построение графика
    plt.figure(figsize=(12, 8))
    
    # График времени выполнения
    plt.subplot(2, 1, 1)
    plt.plot(workers, thread_times, 'bo-', linewidth=2, markersize=8, label='Потоки')
    plt.plot(workers[:len(process_times)], process_times, 'ro-', linewidth=2, markersize=8, label='Процессы')
    plt.xlabel('Количество рабочих единиц', fontsize=12)
    plt.ylabel('Время выполнения (мс)', fontsize=12)
    plt.title(f'Сравнение производительности потоков и процессов (матрица {n}x{n})', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # Добавляем значения на точки
    for i, (w, t) in enumerate(zip(workers, thread_times)):
        plt.text(w, t + max(thread_times)/30, f'{t:.0f}', ha='center', va='bottom', fontsize=9)
    
    for i, (w, t) in enumerate(zip(workers[:len(process_times)], process_times)):
        plt.text(w, t + max(process_times)/30, f'{t:.0f}', ha='center', va='bottom', fontsize=9)
    
    # График ускорения
    plt.subplot(2, 1, 2)
    thread_speedup = [thread_times[0] / t for t in thread_times]
    process_speedup = [process_times[0] / t for t in process_times]
    
    plt.plot(workers, thread_speedup, 'bo-', linewidth=2, markersize=8, label='Потоки')
    plt.plot(workers[:len(process_speedup)], process_speedup, 'ro-', linewidth=2, markersize=8, label='Процессы')
    plt.plot(workers, workers, 'k--', alpha=0.5, label='Идеальное ускорение')
    plt.xlabel('Количество рабочих единиц', fontsize=12)
    plt.ylabel('Коэффициент ускорения', fontsize=12)
    plt.title('Ускорение относительно одного рабочего', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(f'graphs/comparison_{n}x{n}.png', dpi=150, bbox_inches='tight')
    plt.show()
    
    # Анализ результатов
    print("\n" + "="*60)
    print("АНАЛИЗ РЕЗУЛЬТАТОВ:")
    print("="*60)
    
    print(f"\nМатрица: {n}x{n} ({n*n} элементов)")
    
    print("\n1. АБСОЛЮТНОЕ ВРЕМЯ (в миллисекундах):")
    print("   Потоки:  ", end="")
    for w, t in zip(workers, thread_times):
        print(f"{w}т={t:.0f}мс  ", end="")
    
    print("\n   Процессы:", end="")
    for w, t in zip(workers[:len(process_times)], process_times):
        print(f"{w}п={t:.0f}мс  ", end="")
    
    print("\n\n2. УСКОРЕНИЕ (относительно одного рабочего):")
    print("   Потоки:  ", end="")
    for w, s in zip(workers, thread_speedup):
        print(f"{w}т={s:.2f}x  ", end="")
    
    print("\n   Процессы:", end="")
    for w, s in zip(workers[:len(process_speedup)], process_speedup):
        print(f"{w}п={s:.2f}x  ", end="")
    
    print("\n\n3. ЭФФЕКТИВНОСТЬ (ускорение / количество рабочих):")
    for i, w in enumerate(workers):
        if w > 1:
            eff_thread = thread_speedup[i] / w * 100
            print(f"   {w} потоков: эффективность = {eff_thread:.1f}%", end="")
            if i < len(process_speedup):
                eff_process = process_speedup[i] / w * 100
                print(f", {w} процессов: эффективность = {eff_process:.1f}%")
    
    print("\n\n4. ВЫВОДЫ:")
    if thread_times[1] < process_times[1]:
        print("   - Потоки работают быстрее процессов (меньшие накладные расходы)")
    else:
        print("   - Процессы работают быстрее потоков (лучшая изоляция)")
    
    # Находим оптимальное количество
    opt_threads = workers[np.argmin(thread_times[1:]) + 1]
    opt_processes = workers[:len(process_times)][np.argmin(process_times[1:]) + 1]
    
    print(f"   - Оптимальное количество потоков: {opt_threads}")
    print(f"   - Оптимальное количество процессов: {opt_processes}")
    
    if min(thread_times) < min(process_times):
        print(f"   - Лучший результат у потоков: {min(thread_times):.0f} мс")
    else:
        print(f"   - Лучший результат у процессов: {min(process_times):.0f} мс")
    
    print("\n5. ОБЪЯСНЕНИЕ РЕЗУЛЬТАТОВ:")
    print("   - При малом числе рабочих: ускорение близко к линейному")
    print("   - При большом числе рабочих: производительность падает из-за:")
    print("     * Переключения контекста")
    print("     * Конкуренции за доступ к памяти")
    print("     * Накладных расходов синхронизации")
    print("     * Ограничений шины памяти")
    
    print("="*60)

def plot_individual_results():
    """Построение отдельных графиков для потоков и процессов"""
    threads_data = read_results('threads_result.txt')
    processes_data = read_results('processes_result.txt')
    
    # Графики для потоков
    if threads_data:
        plt.figure(figsize=(10, 8))
        colors = plt.cm.tab10(np.linspace(0, 1, len(threads_data)))
        
        for i, (n, times_dict) in enumerate(threads_data.items()):
            workers = sorted(times_dict.keys())
            avg_times = [np.mean(times_dict[w]) for w in workers]
            
            plt.plot(workers, avg_times, 'o-', color=colors[i], linewidth=2, 
                    markersize=8, label=f'{n}x{n}')
            
            # Добавляем значения
            for w, t in zip(workers, avg_times):
                plt.text(w, t + max(avg_times)/20, f'{t:.0f}', 
                        ha='center', va='bottom', fontsize=8)
        
        plt.xlabel('Количество потоков', fontsize=12)
        plt.ylabel('Время выполнения (мс)', fontsize=12)
        plt.title('Производительность многопоточного умножения матриц', 
                 fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)
        plt.legend(title='Размер матрицы')
        plt.tight_layout()
        plt.savefig('graphs/threads_performance.png', dpi=150, bbox_inches='tight')
        plt.show()
    
    # Графики для процессов
    if processes_data:
        plt.figure(figsize=(10, 8))
        colors = plt.cm.tab10(np.linspace(0, 1, len(processes_data)))
        
        for i, (n, times_dict) in enumerate(processes_data.items()):
            workers = sorted(times_dict.keys())
            avg_times = [np.mean(times_dict[w]) for w in workers]
            
            plt.plot(workers, avg_times, 's-', color=colors[i], linewidth=2, 
                    markersize=8, label=f'{n}x{n}')
            
            # Добавляем значения
            for w, t in zip(workers, avg_times):
                plt.text(w, t + max(avg_times)/20, f'{t:.0f}', 
                        ha='center', va='bottom', fontsize=8)
        
        plt.xlabel('Количество процессов', fontsize=12)
        plt.ylabel('Время выполнения (мс)', fontsize=12)
        plt.title('Производительность многопроцессного умножения матриц', 
                 fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)
        plt.legend(title='Размер матрицы')
        plt.tight_layout()
        plt.savefig('graphs/processes_performance.png', dpi=150, bbox_inches='tight')
        plt.show()

def main():
    """Основная функция"""
    print("="*60)
    print("ПОСТРОЕНИЕ ГРАФИКОВ ДЛЯ ЛАБОРАТОРНОЙ РАБОТЫ №2")
    print("="*60)
    
    print("\n1. Построение отдельных графиков...")
    plot_individual_results()
    
    print("\n2. Сравнение потоков и процессов...")
    plot_threads_vs_processes()
    
    print("\n✅ ГРАФИКИ ПОСТРОЕНЫ И СОХРАНЕНЫ В ПАПКУ 'graphs/'")
    print("\nДля просмотра графиков откройте файлы:")
    print("  - graphs/threads_performance.png")
    print("  - graphs/processes_performance.png")
    print("  - graphs/comparison_*.png")
    print("="*60)

if __name__ == "__main__":
    main()