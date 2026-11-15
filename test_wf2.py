import sys
sys.path.insert(0, 'backend/app')
from aegiscore.agent_registry import get_registry
from aegiscore.workflow import OrchestrationWorkflow

with open('wf_debug.txt', 'w') as f:
    f.write('start\n')
    reg = get_registry()
    f.write('reg OK\n')
    wf = OrchestrationWorkflow.__new__(OrchestrationWorkflow)
    f.write('new OK\n')
    # Manually call __init__ steps
    wf.registry = reg
    f.write('registry set\n')
    from aegiscore.agent_base import AgentOrchestrator
    wf.orchestrator = AgentOrchestrator(reg)
    f.write('orchestrator set\n')
    from aegiscore.supervisor import SupervisorAgent
    wf.supervisor = SupervisorAgent(reg)
    f.write('supervisor set\n')
    wf.graph = wf._build_graph()
    f.write('graph built\n')
    f.write('ALL DONE\n')
print('Check wf_debug.txt')