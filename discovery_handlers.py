#!/usr/bin/env python3
"""
Discovery Command Handlers for Harmony Hub Configuration Discovery

This module provides command handler functions for each discovery command,
integrating with existing FastHarmonyHub WebSocket connection management
and adding performance monitoring and metrics collection.
"""

import time
import asyncio
import logging
import functools
import random
from typing import Dict, List, Optional, Any, Tuple, Callable
from config_models import ConfigurationParser, HubInfo
from display_formatter import DisplayFormatter

# Set up logging
logger = logging.getLogger(__name__)


# Network retry mechanism for discovery operations
def discovery_retry(max_attempts: int = 3, base_delay: float = 0.5, max_delay: float = 5.0):
    """
    Decorator for discovery operations with exponential backoff retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 0.5)
        max_delay: Maximum delay in seconds between retries (default: 5.0)
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this is a network-related error that should be retried
                    error_message = str(e).lower()
                    is_network_error = any(keyword in error_message for keyword in [
                        'connection', 'timeout', 'network', 'websocket', 'client', 'server'
                    ])
                    
                    # Don't retry on the last attempt or for non-network errors
                    if attempt == max_attempts - 1 or not is_network_error:
                        break
                    
                    # Calculate exponential backoff delay
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    
                    # Add some jitter to prevent thundering herd
                    jitter = random.uniform(0, 0.1 * delay)
                    total_delay = delay + jitter
                    
                    # Log retry attempt
                    logger.debug(f"Discovery operation retry {attempt + 1}/{max_attempts} after {total_delay:.2f}s: {e}")
                    
                    await asyncio.sleep(total_delay)
            
            # If we get here, all retry attempts failed
            raise last_exception
        
        return wrapper
    return decorator


class PerformanceMonitor:
    """Handles performance monitoring and metrics collection for discovery commands"""
    
    def __init__(self):
        self.metrics = {}
        self.logger = logging.getLogger(__name__ + '.PerformanceMonitor')
    
    async def measure_operation(self, operation_name: str, operation_func, *args, **kwargs) -> Tuple[Any, float]:
        """
        Measure the execution time of an operation
        
        Args:
            operation_name: Name of the operation being measured
            operation_func: Async function to execute and measure
            *args, **kwargs: Arguments to pass to the operation function
            
        Returns:
            Tuple of (operation_result, execution_time_seconds)
        """
        start_time = time.perf_counter()
        
        try:
            result = await operation_func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            
            # Store metrics
            if operation_name not in self.metrics:
                self.metrics[operation_name] = []
            self.metrics[operation_name].append(execution_time)
            
            self.logger.debug(f"Operation '{operation_name}' completed in {execution_time:.3f}s")
            return result, execution_time
            
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            self.logger.error(f"Operation '{operation_name}' failed after {execution_time:.3f}s: {e}")
            raise
    
    def get_metrics_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Get summary of performance metrics
        
        Returns:
            Dictionary with operation names and their performance statistics
        """
        summary = {}
        
        for operation_name, times in self.metrics.items():
            if times:
                summary[operation_name] = {
                    'count': len(times),
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                    'total_time': sum(times)
                }
        
        return summary
    
    def clear_metrics(self):
        """Clear all stored metrics"""
        self.metrics.clear()


class DiscoveryHandlers:
    """Command handlers for discovery operations"""
    
    def __init__(self, hub, verbose: bool = False):
        """
        Initialize discovery handlers
        
        Args:
            hub: FastHarmonyHub instance
            verbose: Whether to enable verbose output
        """
        self.hub = hub
        self.verbose = verbose
        self.parser = ConfigurationParser()
        self.formatter = DisplayFormatter()
        self.performance_monitor = PerformanceMonitor()
        self.logger = logging.getLogger(__name__ + '.DiscoveryHandlers')
    
    @discovery_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def handle_discover(self) -> bool:
        """
        Handle the 'discover' command - retrieve and display complete hub configuration
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.verbose:
                print("🔍 Recupero configurazione completa dal Hub...")
            
            # Measure configuration retrieval performance
            result, exec_time = await self.performance_monitor.measure_operation(
                "get_config", self.hub.get_config_fast
            )
            
            if "error" in result:
                print(f"❌ Errore nel recupero configurazione: {result.get('error', 'Unknown error')}")
                return False
            
            if "data" not in result:
                print("❌ Nessun dato di configurazione ricevuto")
                return False
            
            # Parse the configuration
            parsed_config = self.parser.parse_hub_config(result)
            if not parsed_config:
                print("❌ Errore nel parsing della configurazione")
                return False
            
            # Display the configuration summary
            output = self.formatter.format_discovery_summary(parsed_config)
            print(output)
            
            if self.verbose:
                print(f"⚡ Configurazione recuperata in {exec_time:.3f}s")
                print(f"📊 Trovate {len(parsed_config['activities'])} attività e {len(parsed_config['devices'])} dispositivi")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Discovery command failed: {e}")
            print(f"❌ Errore durante il discovery: {e}")
            return False
    
    @discovery_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def handle_show_activity(self, activity_id: str) -> bool:
        """
        Handle the 'show-activity' command - display detailed activity information
        
        Args:
            activity_id: ID of the activity to display
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.verbose:
                print(f"🎯 Recupero dettagli attività ID: {activity_id}")
            
            # Get full config to find activity details
            result, exec_time = await self.performance_monitor.measure_operation(
                "get_config_for_activity", self.hub.get_config_fast
            )
            
            if "error" in result or "data" not in result:
                print(f"❌ Errore nel recupero configurazione: {result.get('error', 'Unknown error')}")
                return False
            
            # Parse configuration
            parsed_config = self.parser.parse_hub_config(result)
            if not parsed_config:
                print("❌ Errore nel parsing della configurazione")
                return False
            
            # Find the specific activity
            activities = parsed_config.get("activities", [])
            devices = parsed_config.get("devices", [])
            
            activity = None
            for act in activities:
                if str(act.id) == str(activity_id):
                    activity = act
                    break
            
            if not activity:
                print(f"❌ Attività con ID '{activity_id}' non trovata")
                return False
            
            # Display activity details
            output = self.formatter.format_activity_details(activity, devices)
            print(output)
            
            if self.verbose:
                print(f"⚡ Dettagli attività recuperati in {exec_time:.3f}s")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Show activity command failed: {e}")
            print(f"❌ Errore durante il recupero dettagli attività: {e}")
            return False
    
    @discovery_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def handle_show_device(self, device_id: str) -> bool:
        """
        Handle the 'show-device' command - display detailed device information
        
        Args:
            device_id: ID of the device to display
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.verbose:
                print(f"📱 Recupero dettagli dispositivo ID: {device_id}")
            
            # Get full config to find device details
            result, exec_time = await self.performance_monitor.measure_operation(
                "get_config_for_device", self.hub.get_config_fast
            )
            
            if "error" in result or "data" not in result:
                print(f"❌ Errore nel recupero configurazione: {result.get('error', 'Unknown error')}")
                return False
            
            # Parse configuration
            parsed_config = self.parser.parse_hub_config(result)
            if not parsed_config:
                print("❌ Errore nel parsing della configurazione")
                return False
            
            # Find the specific device
            devices = parsed_config.get("devices", [])
            activities = parsed_config.get("activities", [])
            
            device = None
            for dev in devices:
                if str(dev.id) == str(device_id):
                    device = dev
                    break
            
            if not device:
                print(f"❌ Dispositivo con ID '{device_id}' non trovato")
                return False
            
            # Display device details
            output = self.formatter.format_device_details(device, activities)
            print(output)
            
            if self.verbose:
                print(f"⚡ Dettagli dispositivo recuperati in {exec_time:.3f}s")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Show device command failed: {e}")
            print(f"❌ Errore durante il recupero dettagli dispositivo: {e}")
            return False
    
    @discovery_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def handle_show_hub(self, hub_ip: str, remote_id: str) -> bool:
        """
        Handle the 'show-hub' command - display hub information with performance metrics
        
        Args:
            hub_ip: Hub IP address
            remote_id: Hub remote ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.verbose:
                print("🏠 Recupero informazioni Hub...")
            
            # Perform connectivity test and get hub info
            hub_result, hub_exec_time = await self.performance_monitor.measure_operation(
                "get_hub_info", self.hub.get_hub_info_fast
            )
            
            # Get provision info for additional details
            provision_result, provision_exec_time = await self.performance_monitor.measure_operation(
                "get_provision_info", self.hub.get_provision_info_fast
            )
            
            # Test basic connectivity with a status check
            status_result, status_exec_time = await self.performance_monitor.measure_operation(
                "connectivity_test", self.hub.get_current_fast
            )
            
            # Create HubInfo object
            hub_info = HubInfo(
                ip=hub_ip,
                remote_id=remote_id,
                name="Harmony Hub",  # Default name
                firmware_version="Unknown",
                model="Harmony Hub",
                serial_number="Unknown"
            )
            
            # Extract current activity name
            current_activity = None
            connectivity_status = "unknown"
            
            if "data" in hub_result:
                current_activity_data = hub_result["data"].get("current_activity", {})
                if "data" in current_activity_data and "result" in current_activity_data["data"]:
                    activity_id = current_activity_data["data"]["result"]
                    if activity_id == "-1":
                        current_activity = "PowerOff"
                        connectivity_status = "connected"
                    else:
                        current_activity = f"Activity ID: {activity_id}"
                        connectivity_status = "connected"
            
            # Update hub info with provision data if available
            if "data" in provision_result and isinstance(provision_result["data"], dict):
                provision_data = provision_result["data"]
                hub_info.name = provision_data.get("friendlyName", hub_info.name)
                hub_info.firmware_version = provision_data.get("firmwareVersion", hub_info.firmware_version)
                hub_info.model = provision_data.get("model", hub_info.model)
                hub_info.serial_number = provision_data.get("serialNumber", hub_info.serial_number)
            
            # Prepare performance metrics
            performance_metrics = {
                "Hub Info": hub_exec_time,
                "Provision Info": provision_exec_time,
                "Connectivity Test": status_exec_time,
                "Total Response": hub_exec_time + provision_exec_time + status_exec_time
            }
            
            # Display hub information
            output = self.formatter.format_hub_info(
                hub_info, current_activity, connectivity_status, performance_metrics
            )
            print(output)
            
            if self.verbose:
                print(f"⚡ Informazioni Hub recuperate in {sum(performance_metrics.values()):.3f}s totali")
                metrics_summary = self.performance_monitor.get_metrics_summary()
                if metrics_summary:
                    print("📊 Metriche dettagliate:")
                    for op_name, stats in metrics_summary.items():
                        print(f"   {op_name}: {stats['avg_time']:.3f}s avg ({stats['count']} calls)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Show hub command failed: {e}")
            print(f"❌ Errore durante il recupero informazioni Hub: {e}")
            return False
    
    @discovery_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def handle_export_config(self) -> bool:
        """
        Handle the 'export-config' command - export configuration to config.py file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.verbose:
                print("💾 Esportazione configurazione in config.py...")
            
            # Get configuration data
            result, exec_time = await self.performance_monitor.measure_operation(
                "get_config_for_export", self.hub.get_config_fast
            )
            
            if "error" in result or "data" not in result:
                print(f"❌ Errore nel recupero configurazione: {result.get('error', 'Unknown error')}")
                return False
            
            # Parse configuration
            parsed_config = self.parser.parse_hub_config(result)
            if not parsed_config:
                print("❌ Errore nel parsing della configurazione")
                return False
            
            # Export configuration
            try:
                from config_exporter import ConfigExporter
                from config_models import HubInfo
                import config
                
                # Create HubInfo with current configuration
                hub_info = HubInfo(
                    ip=config.HUB_IP,
                    remote_id=config.REMOTE_ID,
                    name="Harmony Hub",
                    firmware_version="Unknown",
                    model="Harmony Hub",
                    serial_number="Unknown"
                )
                
                exporter = ConfigExporter()
                success = exporter.export_to_config_file(parsed_config, hub_info, backup_existing=True)
                if success:
                    print("✅ Configurazione esportata in config.py")
                    print("📁 Backup del file esistente creato")
                    
                    if self.verbose:
                        print(f"⚡ Configurazione esportata in {exec_time:.3f}s")
                        print(f"📊 Esportate {len(parsed_config['activities'])} attività e {len(parsed_config['devices'])} dispositivi")
                    
                    return True
                else:
                    print("❌ Errore durante l'esportazione")
                    return False
                    
            except ImportError:
                print("❌ Config exporter non disponibile")
                return False
            
        except Exception as e:
            self.logger.error(f"Export config command failed: {e}")
            print(f"❌ Errore durante l'esportazione configurazione: {e}")
            return False
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary for all operations
        
        Returns:
            Dictionary containing performance metrics summary
        """
        return self.performance_monitor.get_metrics_summary()
    
    def clear_performance_metrics(self):
        """Clear all performance metrics"""
        self.performance_monitor.clear_metrics()


# Convenience functions for integration with existing CLI
async def handle_discovery_command(hub, command: str, action: Optional[str] = None, 
                                 verbose: bool = False, hub_ip: str = "", remote_id: str = "") -> bool:
    """
    Handle discovery commands with proper error handling and performance monitoring
    
    Args:
        hub: FastHarmonyHub instance
        command: Discovery command to execute
        action: Optional action parameter (for show-activity, show-device)
        verbose: Whether to enable verbose output
        hub_ip: Hub IP address (for show-hub command)
        remote_id: Hub remote ID (for show-hub command)
        
    Returns:
        True if command executed successfully, False otherwise
    """
    handlers = DiscoveryHandlers(hub, verbose)
    
    try:
        if command == "discover":
            return await handlers.handle_discover()
        elif command == "show-activity":
            if not action:
                print("❌ Specifica l'ID dell'attività: harmony.py show-activity <activity_id>")
                return False
            return await handlers.handle_show_activity(action)
        elif command == "show-device":
            if not action:
                print("❌ Specifica l'ID del dispositivo: harmony.py show-device <device_id>")
                return False
            return await handlers.handle_show_device(action)
        elif command == "show-hub":
            return await handlers.handle_show_hub(hub_ip, remote_id)
        elif command == "export-config":
            return await handlers.handle_export_config()
        else:
            print(f"❌ Comando discovery '{command}' non riconosciuto")
            return False
            
    except Exception as e:
        logger.error(f"Discovery command '{command}' failed: {e}")
        print(f"❌ Errore durante l'esecuzione del comando '{command}': {e}")
        return False