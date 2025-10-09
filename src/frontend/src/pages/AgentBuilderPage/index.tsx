import { useState } from "react";
import { Search, Plus, Bot, Clock, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Agent {
  id: string;
  name: string;
  description: string;
  category: string;
  status: "Published" | "Draft";
  timeAgo: string;
  icon: string;
}

const mockAgents: Agent[] = [
  {
    id: "1",
    name: "EHR Connectivity Agent",
    description: "This agent is designed to help EHR providers like Epic, Cerner, and Allscripts...",
    category: "Healthcare",
    status: "Published",
    timeAgo: "6 hrs ago",
    icon: "🏥"
  },
  {
    id: "2", 
    name: "Benefits Check Agent",
    description: "Quickly verify eligibility and coverage details to streamline patient care and reduce...",
    category: "Insurance",
    status: "Draft",
    timeAgo: "1 day ago",
    icon: "💼"
  },
  {
    id: "3",
    name: "Prior Auth Recommendation Agent", 
    description: "Receive automated approval or denial recommendations based on medical necessity...",
    category: "Authorization",
    status: "Draft",
    timeAgo: "6 hrs ago",
    icon: "📋"
  },
  {
    id: "4",
    name: "Auth Guideline",
    description: "Provides step-by-step authorization guidelines and requirements for various medical...",
    category: "Guidelines",
    status: "Published",
    timeAgo: "2 hrs ago",
    icon: "📖"
  }
];

const AgentBuilderPage = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");

  const filteredAgents = mockAgents.filter(agent => 
    agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    agent.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="h-full w-full bg-gradient-to-br from-purple-50 to-indigo-100 dark:from-purple-950 dark:to-indigo-950">
      {/* Header */}
      <div className="">
        <div className="w-full px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                AI Agent Builder
              </h1>
            </div>
          </div>
        </div>
      </div>

      <div className="w-full px-6 py-8 ">
        {/* Welcome Section */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center mx-auto mb-4">
            <Bot className="w-8 h-8 text-purple-600 dark:text-purple-400" />
          </div>
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Hi, What can I help you today?
          </h2>
          <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
            Build workflows from the library of AI Agents, or author your own custom AI Agent
          </p>
        </div>

        {/* Search Bar */}
        <div className="max-w-2xl mx-auto mb-8">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <Input
              type="text"
              placeholder="Describe your agent... e.g., 'Create an agent that can create a clinical summary from a patient chart'"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-12 pr-4 py-4 text-lg border-2 border-purple-200 focus:border-purple-500 rounded-xl bg-white dark:bg-gray-800 dark:border-purple-700"
            />
            <Button 
              className="absolute right-2 top-1/2 transform -translate-y-1/2 bg-purple-600 hover:bg-purple-700 text-white px-6"
              size="sm"
            >
              Start Manually
            </Button>
          </div>
        </div>

        {/* Agents Section */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
              Your Recent Agents (10)
            </h3>
            <Button variant="ghost" className="text-purple-600 hover:text-purple-700">
              View All →
            </Button>
          </div>

          {/* Agent Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredAgents.map((agent) => (
              <Card key={agent.id} className="group hover:shadow-lg transition-all duration-200 border-2 hover:border-purple-200 bg-white dark:bg-gray-800">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center text-lg">
                        {agent.icon}
                      </div>
                      <div>
                        <CardTitle className="text-lg font-semibold text-gray-900 dark:text-white group-hover:text-purple-600 transition-colors">
                          {agent.name}
                        </CardTitle>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge 
                            variant={agent.status === "Published" ? "default" : "secondary"}
                            className={agent.status === "Published" 
                              ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" 
                              : "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200"
                            }
                          >
                            {agent.status}
                          </Badge>
                        </div>
                      </div>
                    </div>
                    <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <Star className="w-4 h-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-gray-600 dark:text-gray-400 mb-4 line-clamp-2">
                    {agent.description}
                  </CardDescription>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-1 text-sm text-gray-500 dark:text-gray-400">
                      <Clock className="w-4 h-4" />
                      <span>{agent.timeAgo}</span>
                    </div>
                    <Button 
                      size="sm" 
                      className="bg-purple-600 hover:bg-purple-700 text-white"
                    >
                      Open
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentBuilderPage;