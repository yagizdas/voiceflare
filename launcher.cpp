#include <iostream>
#include <windows.h>
#include <string>

int main() {
    // Get the directory where the .exe is located
    char exePath[MAX_PATH];
    GetModuleFileNameA(NULL, exePath, MAX_PATH);
    std::string exeDir(exePath);
    exeDir = exeDir.substr(0, exeDir.find_last_of("\\/"));
    
    // Change to the script directory
    SetCurrentDirectoryA(exeDir.c_str());
    
    // Build the command to run Python
    std::string command = "python bot_full.py";
    
    std::cout << "Starting Discord Bot..." << std::endl;
    std::cout << "Running: " << command << std::endl;
    std::cout << "Working directory: " << exeDir << std::endl;
    std::cout << "----------------------------------------" << std::endl;
    
    // Run the Python script
    int result = system(command.c_str());
    
    if (result != 0) {
        std::cerr << "\nError: Failed to run Python script (exit code: " << result << ")" << std::endl;
        std::cerr << "Make sure Python is installed and in your PATH" << std::endl;
        std::cout << "\nPress Enter to exit...";
        std::cin.get();
        return 1;
    }
    
    return 0;
}
