#include <Python.h>
#include <import.h>
#include <graminit.h>
#include <pythonrun.h>

void error(char *msg) { 
	PyErr_Print();
	printf("%s\n", msg); 
	exit(1); 
}

char* python_code = "\
import os\n\
sys.path.insert(0,os.getcwd())\n\
print sys.path\n\
elements = locals()\n\
lista = [k for k in elements['arguments'] if type(k) == str]\n\
sys.argv = lista\n\
from libchristine.libs_christine import sanity\n\
sanity()\n\
#sys.exit()\n\
from libchristine.Christine import *\n\
a = Christine()\n\
if len(sys.argv) > 1 and not \"--devel\" in sys.argv:\n\
	for i in sys.argv[1:]:\n\
		if os.path.isfile(i):\n\
			a.Queue.add(i,prepend=True)\n\
	a.play()\n\
a.runGtk()\n\
";


int
main(int argc, char *argv[]){
	PyObject *t,*main_module, *main_dict, *main_dict_copy;
	PyObject *builtinMod,*c_argv;
	int i;
	Py_Initialize();
	// Get a reference to the main module
	main_module = PyImport_AddModule("__main__");
	if (main_module == NULL)
		error ("Could not import __main__ module");
	main_dict = PyModule_GetDict(main_module);
	if (main_dict == NULL)
		error ("Could not get the __main__ module dictionary");
	if (PyDict_GetItemString(main_dict, "__import__") == NULL){
	        builtinMod = PyImport_ImportModule("__builtin__");
			PyObject *sys = PyImport_ImportModule("sys");
			if (sys == NULL)
				error("");
			PyObject *bdict = PyModule_GetDict(sys);
	        if (builtinMod == NULL)
				error("Could not import the __builtins__ module");
			if (PyDict_SetItemString(main_dict, "__builtins__", builtinMod) != 0)
				error("Could not assign the new dictionary");
			if (PyDict_SetItemString(main_dict,"sys", sys) !=0)
				error("");
			if (PyDict_GetItemString(main_dict, "__builtins__") == NULL)
				error ("Still there is no __builtins__!!!!");
			PyObject  *keys = PyDict_Keys(bdict);
			PyList_Sort(keys);
	}
	c_argv = PyList_New(0);
	if (c_argv == NULL)
		error("");
	for (i = 0; i < argc ;i++){
		if (PyList_Append(c_argv, PyString_FromString(argv[i]))!=0)
			error("");
	}
	PyDict_SetItemString(main_dict,"arguments",c_argv);
	main_dict_copy = PyDict_Copy(main_dict);
	if (main_dict_copy == NULL)
		error ("asdfa");
	t = PyRun_String(python_code,Py_file_input,main_dict,main_dict);
	if (t == NULL){
		error("Error while trying to run christine");
	}
	//Py_DECREF(t);
	Py_Finalize();
	return 0;
}


