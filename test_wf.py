import sys, time
from multiprocessing import Process

def construct_workflow():
    sys.path.insert(0, 'backend/app')
    from aegiscore.agent_registry import get_registry
    reg = get_registry()
    print(f"Registry OK: {reg.list_agents()}", flush=True)
    
    from aegiscore.workflow import OrchestrationWorkflow
    print("Workflow module imported", flush=True)
    
    wf = OrchestrationWorkflow(reg)
    print("OrchestrationWorkflow constructed OK", flush=True)

if __name__ == '__main__':
    p = Process(target=construct_workflow)
    p.start()
    p.join(timeout=15)
    if p.is_alive():
        p.terminate()
        p.join()
        print("TIMEOUT: OrchestrationWorkflow construction took >15s", flush=True)
    else:
        print("Completed within timeout", flush=True)
    print("DONE", flush=True)