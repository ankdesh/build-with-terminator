import sys
import os

def main():
    print("Starting log-analyis-client...")
    
    # Add the build directory to path so we can find the compiled worker
    sys.path.append(os.path.join(os.getcwd(), "build"))
    
    try:
        import worker
        print(f"C++ Extension says: {worker.hello()}")
    except ImportError as e:
        print(f"Could not load C++ worker extension: {e}")
        print("Make sure you have built the C++ project in the 'build' directory.")

if __name__ == "__main__":
    main()
