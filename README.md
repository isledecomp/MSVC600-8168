# MSVC 12.00.8804 for 80x86 toolchain (Visual Studio 6.0)

This repo contains the MSVC6 toolchain with the following additional (Unix-only) support:
- wrappers based on [msvc-wine](https://github.com/mstorsjo/msvc-wine): allowing cl use in your shell terminal 
- dependency tracking by parsing [SBR files](https://learn.microsoft.com/en-us/cpp/build/reference/fr-fr-create-dot-sbr-file): allowing use of the CMake Unix Makefiles and Ninja generators.

# Version strings

- CL.EXE: 12.00.8168
- LINK.EXE: 6.00.8168

# How to use?

1. In your terminal, run `source <path-to-MSVC600-8168>/activate_x86` to configure your environment variables.
These changes are only active as long as your terminal session.
2. Start building!

# CMake

After settings the environment variables using `activate_x86`, configure your project with the following additional configure arguments:
```sh
-DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_C_DEPFILE_FORMAT=msvc -DCMAKE_DEPFILE_FLAGS_C=/showIncludes -DCMAKE_CXX_DEPFILE_FORMAT=msvc -DCMAKE_DEPFILE_FLAGS_CXX=/showIncludes
```
For parallel builds, make sure you're **NOT** using the [`ProgramDatabase`](https://cmake.org/cmake/help/latest/prop_tgt/MSVC_DEBUG_INFORMATION_FORMAT.html#prop_tgt:MSVC_DEBUG_INFORMATION_FORMAT) debug format.
Use [`/Z7` instead of `/Zi`](https://learn.microsoft.com/en-us/cpp/build/reference/z7-zi-zi-debug-information-format).

CLion users on Linux can use this toolchain by adding a custom toolchain that uses the `activate_x86` environment file.
Also manually set the C and C++ compiler to `cl`.

# Speeding up wine

Optionally, but advisable because it makes everything much faster: start a persistent wineserver. 

```
wineserver -k # Kill a potential old server
wineserver -p # Start a new server
wine64 wineboot # Run a process to start up all background wine processes
```

# What about Windows?

Windows users can set `VC/Bin/VCVARS32.BAT` to configure environment variables.

Dependency tracking is not implemented for Windows.
You'd need to develop a cl.exe wrapper script that adds the appropriate argument to create a SBR, calls the original CL.EXE, and then parses the SBR. 
Contributions are welcome.

CLion users can add [this toolchain](https://www.jetbrains.com/help/clion/how-to-create-toolchain-in-clion.html#compdb-toolchain): use the Visual Studio type, and point to the location where you cloned this repo. Don't forget to select the `NMake Makefiles` CMake generator. 

# Bugs?

We'd like to get rid of the need to configure with `-DCMAKE_<lang>_DEPFILE_FORMAT=msvc -DCMAKE_DEPFILE_FLAGS_C<lang>=/showIncludes`.
It's explicitly disabled [here](https://github.com/Kitware/CMake/blob/2ff29900491e4f8a97f80fbd647c11dfd4cf74b0/Modules/Platform/Windows-MSVC.cmake#L567-L571).
However, enabling causes CMake configuration to fail miserably.
If you know how to fix this, please let us know and send patches to [kitware](https://gitlab.kitware.com/cmake/cmake).

