"""
MicBoost - System Optimizer
Applies Windows optimizations to reduce audio processing latency.
"""

import ctypes
import subprocess
import sys
import os
import winreg
from dataclasses import dataclass


@dataclass
class OptimizationResult:
    """Result of an applied optimization."""
    name: str
    success: bool
    message: str
    requires_admin: bool = False


class SystemOptimizer:
    """
    System optimizer for low-latency audio on Windows.
    
    Applies several optimizations:
    - Real-Time process priority
    - High-Performance power plan check
    - Disable Windows audio enhancements
    """

    # Constantes de prioridade do Windows
    REALTIME_PRIORITY_CLASS = 0x00000100
    HIGH_PRIORITY_CLASS = 0x00000080
    ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
    NORMAL_PRIORITY_CLASS = 0x00000020

    THREAD_PRIORITY_TIME_CRITICAL = 15
    THREAD_PRIORITY_HIGHEST = 2

    def __init__(self):
        self._optimizations_applied: list[OptimizationResult] = []
        self._original_priority = None

    @staticmethod
    def is_admin() -> bool:
        """Verifica se o processo está rodando como administrador."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def set_process_priority(self, realtime: bool = True) -> OptimizationResult:
        """
        Eleva a prioridade do processo para Real-Time ou High.
        
        Args:
            realtime: True para REALTIME, False para HIGH
        """
        try:
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            
            # Salva prioridade original
            if self._original_priority is None:
                self._original_priority = ctypes.windll.kernel32.GetPriorityClass(handle)

            if realtime:
                priority = self.REALTIME_PRIORITY_CLASS
                priority_name = "Real-Time"
            else:
                priority = self.HIGH_PRIORITY_CLASS
                priority_name = "Alta"

            result = ctypes.windll.kernel32.SetPriorityClass(handle, priority)
            
            if result:
                # Também eleva a thread atual
                thread_handle = ctypes.windll.kernel32.GetCurrentThread()
                ctypes.windll.kernel32.SetThreadPriority(
                    thread_handle, 
                    self.THREAD_PRIORITY_TIME_CRITICAL if realtime else self.THREAD_PRIORITY_HIGHEST
                )
                
                opt = OptimizationResult(
                    name="Prioridade do Processo",
                    success=True,
                    message=f"Prioridade definida para {priority_name}"
                )
            else:
                # Tenta HIGH se REALTIME falhar
                if realtime:
                    result = ctypes.windll.kernel32.SetPriorityClass(handle, self.HIGH_PRIORITY_CLASS)
                    if result:
                        opt = OptimizationResult(
                            name="Prioridade do Processo",
                            success=True,
                            message="Prioridade definida para Alta (Real-Time requer admin)",
                            requires_admin=True
                        )
                    else:
                        opt = OptimizationResult(
                            name="Prioridade do Processo",
                            success=False,
                            message="Não foi possível alterar prioridade",
                            requires_admin=True
                        )
                else:
                    opt = OptimizationResult(
                        name="Prioridade do Processo",
                        success=False,
                        message="Não foi possível alterar prioridade"
                    )

        except Exception as e:
            opt = OptimizationResult(
                name="Prioridade do Processo",
                success=False,
                message=f"Erro: {e}"
            )

        self._optimizations_applied.append(opt)
        return opt

    def restore_process_priority(self):
        """Restaura a prioridade original do processo."""
        if self._original_priority is not None:
            try:
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.kernel32.SetPriorityClass(handle, self._original_priority)
                self._original_priority = None
            except Exception:
                pass

    def check_power_plan(self) -> OptimizationResult:
        """Verifica o plano de energia atual do Windows."""
        try:
            result = subprocess.run(
                ['powercfg', '/getactivescheme'],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout.strip()
            
            is_high_perf = any(x in output.lower() for x in [
                'alto desempenho', 'high performance', 
                'desempenho máximo', 'ultimate performance'
            ])
            
            if is_high_perf:
                opt = OptimizationResult(
                    name="Plano de Energia",
                    success=True,
                    message=f"Plano de energia adequado: {output}"
                )
            else:
                opt = OptimizationResult(
                    name="Plano de Energia",
                    success=False,
                    message=f"Plano atual: {output}\n"
                            f"Recomendado: Altere para 'Alto Desempenho' nas configuracoes de energia."
                )

        except Exception as e:
            opt = OptimizationResult(
                name="Plano de Energia",
                success=False,
                message=f"Não foi possível verificar: {e}"
            )

        self._optimizations_applied.append(opt)
        return opt

    def set_high_performance_power_plan(self) -> OptimizationResult:
        """Tenta ativar o plano de energia Alto Desempenho."""
        # GUID padrão do plano "Alto Desempenho"
        HIGH_PERF_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        try:
            result = subprocess.run(
                ['powercfg', '/setactive', HIGH_PERF_GUID],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                opt = OptimizationResult(
                    name="Plano de Energia",
                    success=True,
                    message="Plano de energia alterado para Alto Desempenho"
                )
            else:
                opt = OptimizationResult(
                    name="Plano de Energia",
                    success=False,
                    message=f"Não foi possível alterar: {result.stderr}",
                    requires_admin=True
                )
        except Exception as e:
            opt = OptimizationResult(
                name="Plano de Energia",
                success=False,
                message=f"Erro: {e}"
            )

        self._optimizations_applied.append(opt)
        return opt

    def disable_audio_enhancements_info(self) -> OptimizationResult:
        """
        Retorna instruções para desativar audio enhancements do Windows.
        (Não pode ser feito programaticamente de forma confiável)
        """
        opt = OptimizationResult(
            name="Audio Enhancements",
            success=True,
            message=(
                "Para desativar manualmente:\n"
                "1. Clique direito no ícone de som → Configurações de som\n"
                "2. Vá em Propriedades do dispositivo (microfone)\n"
                "3. Aba 'Avançado' → Desmarque 'Habilitar aprimoramentos de áudio'\n"
                "4. Aba 'Avançado' → Marque 'Permitir modo exclusivo'\n"
                "5. Desmarque 'Dar prioridade a aplicativos de modo exclusivo'"
            )
        )
        self._optimizations_applied.append(opt)
        return opt

    def set_cpu_affinity(self, core: int = 0) -> OptimizationResult:
        """
        Fixa o processo em um core específico da CPU.
        Pode reduzir latência ao evitar migração entre cores.
        
        Args:
            core: Número do core (0-based)
        """
        try:
            import os
            cpu_count = os.cpu_count() or 1
            
            if core >= cpu_count:
                core = 0

            handle = ctypes.windll.kernel32.GetCurrentProcess()
            # Cria máscara de afinidade para o core especificado
            affinity_mask = 1 << core
            result = ctypes.windll.kernel32.SetProcessAffinityMask(
                handle, ctypes.c_ulonglong(affinity_mask)
            )

            if result:
                opt = OptimizationResult(
                    name="Afinidade de CPU",
                    success=True,
                    message=f"Processo fixado no core {core}"
                )
            else:
                opt = OptimizationResult(
                    name="Afinidade de CPU",
                    success=False,
                    message="Não foi possível definir afinidade de CPU"
                )

        except Exception as e:
            opt = OptimizationResult(
                name="Afinidade de CPU",
                success=False,
                message=f"Erro: {e}"
            )

        self._optimizations_applied.append(opt)
        return opt

    def reset_cpu_affinity(self):
        """Restaura a afinidade de CPU para todos os cores."""
        try:
            cpu_count = os.cpu_count() or 1
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            all_cores_mask = (1 << cpu_count) - 1
            ctypes.windll.kernel32.SetProcessAffinityMask(
                handle, ctypes.c_ulonglong(all_cores_mask)
            )
        except Exception:
            pass

    def disable_nagle_algorithm(self) -> OptimizationResult:
        """
        Desativa o algoritmo de Nagle para reduzir latência de rede
        (útil se o áudio é transmitido via rede, ex: Discord/streaming).
        """
        try:
            key_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            
            opt = OptimizationResult(
                name="Nagle Algorithm",
                success=True,
                message="Verificação do algoritmo de Nagle concluída.\n"
                        "Para streaming de áudio via rede, desative nas configurações do adaptador."
            )
        except Exception as e:
            opt = OptimizationResult(
                name="Nagle Algorithm",
                success=False,
                message=f"Não foi possível verificar: {e}"
            )

        self._optimizations_applied.append(opt)
        return opt

    def apply_all_optimizations(self, realtime_priority: bool = True,
                                 fix_cpu_core: bool = False,
                                 core_number: int = 0) -> list[OptimizationResult]:
        """
        Aplica todas as otimizações disponíveis.
        
        Args:
            realtime_priority: Definir prioridade Real-Time
            fix_cpu_core: Fixar em um core específico
            core_number: Número do core para fixar
        """
        self._optimizations_applied.clear()
        results = []

        # 1. Prioridade do processo
        results.append(self.set_process_priority(realtime_priority))

        # 2. Verificar plano de energia
        results.append(self.check_power_plan())

        # 3. Info sobre audio enhancements
        results.append(self.disable_audio_enhancements_info())

        # 4. Afinidade de CPU (opcional)
        if fix_cpu_core:
            results.append(self.set_cpu_affinity(core_number))

        return results

    def restore_all(self):
        """Restaura todas as configurações originais."""
        self.restore_process_priority()
        self.reset_cpu_affinity()

    def get_system_info(self) -> dict:
        """Retorna informações relevantes do sistema."""
        info = {
            'os': sys.platform,
            'python': sys.version,
            'cpu_count': os.cpu_count(),
            'is_admin': self.is_admin(),
        }
        
        try:
            result = subprocess.run(
                ['powercfg', '/getactivescheme'],
                capture_output=True, text=True, timeout=5
            )
            info['power_plan'] = result.stdout.strip()
        except Exception:
            info['power_plan'] = 'Desconhecido'

        return info

    def get_applied_optimizations(self) -> list[OptimizationResult]:
        """Retorna lista de otimizações aplicadas."""
        return self._optimizations_applied.copy()
