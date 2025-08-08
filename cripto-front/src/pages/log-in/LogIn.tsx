import LogInForm from "../../components/forms/LogInForm"

const LogInPage = () => {

    return(
        <div className="flex justify-center items-center min-h-screen p-4"> 
            <main className="flex flex-col border-2 rounded-md gap-4 w-full sm:w-2/3 
            md:w-1/2 lg:w-1/3 p-4 bg-amber-600 dark:bg-amber-950">
                <h1 className="flex justify-center text-2xl">Inicar Sesión</h1>
                <section className="">
                    <LogInForm></LogInForm>
                </section>
            </main>
        </div>
    )

}

export default LogInPage